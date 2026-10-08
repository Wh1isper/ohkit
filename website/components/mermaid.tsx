"use client";

import { useEffect, useId, useRef, useState } from "react";
import { useTheme } from "next-themes";
import { renderDiagram } from "@/lib/mermaid";

function Diagram({
  chart,
  fullSize = false,
}: {
  chart: string;
  fullSize?: boolean;
}) {
  const id = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const { resolvedTheme } = useTheme();
  const [diagram, setDiagram] = useState<{ svg: string; width: number }>();
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    setFailed(false);
    void renderDiagram(`diagram-${id}`, chart, resolvedTheme === "dark").then(
      (result) => {
        if (active) setDiagram(result);
      },
      () => {
        if (active) setFailed(true);
      },
    );
    return () => {
      active = false;
    };
  }, [chart, id, resolvedTheme]);

  if (failed)
    return (
      <p role="alert" className="diagram-status">
        The diagram could not be rendered. Its source is available below.
      </p>
    );
  if (!diagram)
    return (
      <p role="status" className="diagram-status">
        Rendering diagram…
      </p>
    );
  return (
    <div
      className="diagram-svg"
      style={{ minWidth: diagram.width * (fullSize ? 1 : 0.8) }}
      dangerouslySetInnerHTML={{ __html: diagram.svg }}
    />
  );
}

export function Mermaid({ chart }: { chart: string }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [expanded, setExpanded] = useState(false);
  const titleId = useId();

  return (
    <figure className="diagram not-prose">
      <figcaption className="diagram-toolbar">
        <span>Architecture diagram</span>
        <button
          type="button"
          onClick={() => {
            setExpanded(true);
            dialog.current?.showModal();
          }}
        >
          Expand <span aria-hidden="true">↗</span>
        </button>
      </figcaption>
      <div
        className="diagram-canvas"
        tabIndex={0}
        role="region"
        aria-label="Diagram, scroll horizontally to explore"
      >
        <Diagram chart={chart} />
      </div>
      <details className="diagram-source">
        <summary>View Mermaid source</summary>
        <pre>
          <code>{chart}</code>
        </pre>
      </details>
      <dialog
        ref={dialog}
        className="diagram-dialog"
        aria-labelledby={titleId}
        onClose={() => setExpanded(false)}
        onClick={(event) => {
          if (event.target === dialog.current) dialog.current.close();
        }}
      >
        <div className="diagram-toolbar">
          <h2 id={titleId}>Architecture diagram</h2>
          <button
            type="button"
            onClick={() => dialog.current?.close()}
            autoFocus
          >
            Close <span aria-hidden="true">×</span>
          </button>
        </div>
        <div
          className="diagram-canvas"
          tabIndex={0}
          role="region"
          aria-label="Expanded diagram, scroll to explore"
        >
          {expanded && <Diagram chart={chart} fullSize />}
        </div>
      </dialog>
    </figure>
  );
}
