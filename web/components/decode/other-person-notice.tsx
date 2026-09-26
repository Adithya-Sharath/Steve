/**
 * Shown at the top of the screen while the microphone is live, so the other person can read it (D47).
 * The Arabic line is marked for native-speaker review in `copy_review.md`: it was written by the developers and has not been checked.
 */
export function OtherPersonNotice() {
  return (
    <div role="status" aria-live="polite" className="rounded-2xl border-2 border-primary bg-teal-soft px-4 py-3 text-foreground" data-testid="other-person-notice">
      <p className="text-lg font-medium" lang="en">
        <span aria-hidden>🎧</span> Steve is helping me understand. Nothing is recorded.
      </p>
      <p className="mt-1 text-lg font-medium" lang="ar" dir="rtl">
        ستيف يساعدني على الفهم. لا يتم تسجيل أي شيء.
      </p>
    </div>
  );
}
