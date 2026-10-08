import Link from "next/link";
import { HomeLayout } from "fumadocs-ui/layouts/home";
import { getMDXComponents } from "@/components/mdx";
import { source } from "@/lib/source";
import { layoutOptions, site } from "@/lib/site";

export const metadata = { alternates: { canonical: "/" } };

export default function Home() {
  const page = source.getPage([])!;
  const MDX = page.data.body;
  return (
    <HomeLayout {...layoutOptions}>
      <div className="home">
        <section className="hero" aria-labelledby="hero-title">
          <div className="hero-copy">
            <span className="eyebrow">Pre-alpha bootstrap · Python 3.13+</span>
            <h1 id="hero-title">
              Agent harnesses.
              <br />
              <span>A Python interface.</span>
            </h1>
            <p className="hero-description">
              Keep the native agent loop.
              <br />
              Give your application a clear execution boundary.
            </p>
            <div className="hero-actions">
              <Link className="primary-link" href="/getting-started/">
                Get started <span aria-hidden="true">→</span>
              </Link>
              <Link
                className="secondary-link"
                href="/examples/application-hosted-executor/"
              >
                Explore the design <span aria-hidden="true">↗</span>
              </Link>
            </div>
            <div className="install-command">
              <span aria-hidden="true">$</span>
              <code>python -m pip install --pre ohkit</code>
            </div>
          </div>
          <div
            className="architecture-card"
            aria-label="Design: the application calls ohkit; native harnesses own execution"
          >
            <div className="card-caption">
              THE EXECUTION BOUNDARY <span>Design preview</span>
            </div>
            <div className="architecture-layer">
              <strong>Your application</strong>
              <span>Policy · persistence · delivery</span>
            </div>
            <div className="architecture-connector" aria-hidden="true">
              ↓
            </div>
            <div className="architecture-layer core-layer">
              <strong>ohkit</strong>
              <span>
                Thread <i /> Run <i /> Workspace
              </span>
            </div>
            <div className="architecture-connector" aria-hidden="true">
              ↓
            </div>
            <div className="architecture-layer">
              <strong>Native agent harness</strong>
              <span>Agent loop · tools · history</span>
            </div>
            <p>One boundary. Explicit ownership.</p>
          </div>
        </section>
        <div className="home-content prose">
          <MDX components={getMDXComponents(page)} />
        </div>
        <footer className="home-footer">
          <span>ohkit · An independent project by Wh1isper</span>
          <a href={site.repository}>Source on GitHub ↗</a>
        </footer>
      </div>
    </HomeLayout>
  );
}
