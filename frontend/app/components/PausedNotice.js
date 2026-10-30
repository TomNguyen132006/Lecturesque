import Link from 'next/link'
import { DEMO_VIDEO_URL, README_URL } from '../lib/paused'

// Shown instead of the error when the AI key is switched off. Nothing here navigates by itself.
export default function PausedNotice() {
  return (
    <div role="alert" className="flex flex-col gap-4 rounded-3xl bg-accent px-4 py-5 text-accent-foreground sm:px-6">
      <div>
        <p className="font-serif text-2xl leading-tight">Out of credits: live runs are paused</p>
        <p className="mt-2">
          This demo&apos;s AI credits are switched off, so new lectures can&apos;t be processed right now. You can still watch the demo video, open the example,
          or run Lecturesque locally with your own key (see the README).
        </p>
      </div>
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
        <a href={DEMO_VIDEO_URL} target="_blank" rel="noopener noreferrer" className="story-button story-button-coral story-button-small">
          Watch the demo video
        </a>
        <Link href="/app/job/example-strang" className="story-button story-button-forest story-button-small">
          Open the example
        </Link>
        <a href={README_URL} target="_blank" rel="noopener noreferrer" className="story-button story-button-outline story-button-small">
          Read the README
        </a>
      </div>
    </div>
  )
}
