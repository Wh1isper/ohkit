import Link from "next/link";

export default function NotFound() {
  return (
    <main className="not-found">
      <span className="eyebrow">404 · ohkit</span>
      <h1>Page not found</h1>
      <p>This address does not match a documentation page.</p>
      <Link className="primary-link" href="/">
        Back to documentation →
      </Link>
    </main>
  );
}
