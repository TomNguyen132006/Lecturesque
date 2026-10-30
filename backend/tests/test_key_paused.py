"""A missing or rejected AI key (AI_KEY_UNAVAILABLE): fails at once, no retry, no leak, and the day's job slot is given back.
Everything is mocked: no network, no real key (the fake key below is not a secret)."""
import json
from types import SimpleNamespace

import httpx2 as httpx  # openai 3.x ships httpx2, not httpx
import openai
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

import clean
import jobs_api
import llm
import pipeline
import topics
from schemas import Job, Segment
from storage import get_storage

FAKE_KEY = "test-key-123"
REQUEST = httpx.Request("POST", "https://example.invalid/v1/chat/completions")
MESSAGES = [{"role": "user", "content": "hello"}]


def rejected(code):
    cls = openai.AuthenticationError if code == 401 else openai.PermissionDeniedError
    response = httpx.Response(code, request=REQUEST, text=f"bad key {FAKE_KEY}")  # the provider body even repeats the key
    return cls(f"http {code} {FAKE_KEY}", response=response, body=None)


class FakeClient:
    def __init__(self, error):
        self.error, self.calls = error, 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls += 1
        raise self.error


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    sleeps = []
    monkeypatch.setattr(llm, "_sleep", sleeps.append)
    monkeypatch.setattr(llm, "_rejected_key", None)
    monkeypatch.setenv("LLM_LOG_PATH", str(tmp_path / "calls.jsonl"))
    return SimpleNamespace(sleeps=sleeps, log=tmp_path / "calls.jsonl")


def call(client=None):
    return llm.call_model("nano", MESSAGES, job_id="job_k1", stage="cleaning", max_tokens=10, client=client)


@pytest.mark.parametrize("value", [None, "", "   "])
def test_missing_key_fails_at_once_without_a_network_call(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    else:
        monkeypatch.setenv("NEBIUS_API_KEY", value)
    monkeypatch.setattr(llm, "OpenAI", lambda **kw: pytest.fail("no client may be built without a key"))
    with pytest.raises(llm.LLMKeyError) as caught:
        call()
    assert "AI_KEY_UNAVAILABLE" in str(caught.value) and caught.value.attempts == 0


@pytest.mark.parametrize("code", [401, 403])
def test_rejected_key_is_not_retried(isolated, code):
    client = FakeClient(rejected(code))
    with pytest.raises(llm.LLMKeyError) as caught:
        call(client)
    assert client.calls == 1 and isolated.sleeps == [] and caught.value.status_code == code


def test_after_one_rejection_the_same_key_makes_no_more_calls(monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", FAKE_KEY)
    fake = FakeClient(rejected(401))
    monkeypatch.setattr(llm, "OpenAI", lambda **kw: fake)
    for _ in range(3):
        with pytest.raises(llm.LLMKeyError):
            call()
    assert fake.calls == 1  # the 2nd and 3rd failed before any request
    monkeypatch.setenv("NEBIUS_API_KEY", "another-key-456")  # a new key is tried again
    with pytest.raises(llm.LLMKeyError):
        call()
    assert fake.calls == 2


def test_the_key_never_appears_in_errors_logs_or_output(monkeypatch, isolated, capsys, caplog):
    monkeypatch.setenv("NEBIUS_API_KEY", FAKE_KEY)
    monkeypatch.setattr(llm, "OpenAI", lambda **kw: FakeClient(rejected(401)))
    with pytest.raises(llm.LLMKeyError) as caught:
        call()
    shown = [str(caught.value), repr(caught.value), str(caught.value.__cause__), isolated.log.read_text(encoding="utf-8"),
             capsys.readouterr().out, capsys.readouterr().err, caplog.text]
    assert all(FAKE_KEY not in text for text in shown)
    assert "HTTP 401" in str(caught.value) and "bad key" not in str(caught.value)  # the provider's body is not passed on


def test_a_rejected_key_stops_cleaning_and_topics_instead_of_falling_back():
    segments = [Segment(id="seg_0001", start=0, end=5, text="hello there")]
    client = FakeClient(rejected(401))
    with pytest.raises(llm.LLMKeyError):
        clean.clean_transcript(segments, job_id="job_k1", client=client, max_workers=1)
    with pytest.raises(llm.LLMKeyError):
        topics.split_topics(segments, job_id="job_k1", client=client)
    assert client.calls == 2


def test_other_llm_errors_are_still_swallowed_per_batch():
    segments = [Segment(id="seg_0001", start=0, end=5, text="hello there")]
    boom = openai.BadRequestError("bad", response=httpx.Response(400, request=REQUEST), body=None)
    result = clean.clean_transcript(segments, job_id="job_k1", client=FakeClient(boom), max_workers=1)
    assert result.segments[0].text == "hello there" and result.report["reverted_by_reason"] == {"llm_error": 1}


def test_pipeline_job_error_is_the_stable_code(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("NEBIUS_API_KEY", FAKE_KEY)
    storage = get_storage()
    pipeline.create_job("job_k1", "lecture.srt", b"x", storage)
    ran = []
    monkeypatch.setattr(pipeline, "_transcribe_stage", lambda *a: ran.append("t"))
    monkeypatch.setattr(pipeline, "_clean_stage", lambda *a: (_ for _ in ()).throw(llm.LLMKeyError(f"AI_KEY_UNAVAILABLE {FAKE_KEY}")))
    monkeypatch.setattr(pipeline, "_enrich_stage", lambda *a: ran.append("e"))
    job = pipeline.run_pipeline("job_k1", "lecture.srt", storage)
    assert (job.status, job.error) == ("error", "cleaning: AI_KEY_UNAVAILABLE") and ran == ["t"]
    saved = json.dumps(pipeline.load_job("job_k1", storage).model_dump())
    assert FAKE_KEY not in saved


def upload_with(monkeypatch, tmp_path, outcome):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setattr(jobs_api, "limiter", jobs_api.JobLimiter())
    monkeypatch.setattr(pipeline, "run_pipeline", lambda job_id, name, storage=None: Job(id=job_id, status="error", stage="cleaning", error=outcome))
    app = FastAPI()
    app.include_router(jobs_api.router)
    srt = "1\n00:00:00,000 --> 00:00:05,000\nhello\n".encode()
    assert TestClient(app).post("/jobs", files={"file": ("lecture.srt", srt)}).status_code == 200
    return jobs_api.limiter


def test_a_paused_job_does_not_use_up_the_days_count(monkeypatch, tmp_path):
    limiter = upload_with(monkeypatch, tmp_path, "cleaning: AI_KEY_UNAVAILABLE")
    assert (limiter.today, limiter.running) == (0, 0)


def test_a_normal_failure_still_counts(monkeypatch, tmp_path):
    limiter = upload_with(monkeypatch, tmp_path, "cleaning: model is down")
    assert (limiter.today, limiter.running) == (1, 0)
