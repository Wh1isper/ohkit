// Mermaid's configuration is global. Serialize configuration + rendering so
// multiple diagrams and theme changes cannot borrow each other's palette.
let pending: Promise<unknown> = Promise.resolve();

export function renderDiagram(id: string, chart: string, dark: boolean) {
  const task = pending.then(async () => {
    const { default: mermaid } = await import("mermaid");
    const p = dark
      ? {
          surface: "#26262c",
          border: "#71717a",
          text: "#e8e8ec",
          line: "#a1a1aa",
          muted: "#1e1e23",
          note: "#303038",
        }
      : {
          surface: "#f0f0f4",
          border: "#a1a1aa",
          text: "#27272a",
          line: "#71717a",
          muted: "#fafafa",
          note: "#e8e8ee",
        };
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      suppressErrorRendering: true,
      theme: "base",
      look: "classic",
      fontFamily: getComputedStyle(document.body).fontFamily,
      fontSize: 14,
      flowchart: {
        htmlLabels: false,
        nodeSpacing: 28,
        rankSpacing: 42,
        padding: 16,
        wrappingWidth: 180,
        curve: "basis",
      },
      sequence: {
        width: 150,
        height: 44,
        actorMargin: 36,
        messageMargin: 32,
        mirrorActors: false,
        wrap: true,
      },
      themeVariables: {
        darkMode: dark,
        fontSize: "14px",
        primaryColor: p.surface,
        primaryTextColor: p.text,
        primaryBorderColor: p.border,
        lineColor: p.line,
        secondaryColor: p.muted,
        tertiaryColor: p.muted,
        clusterBkg: p.muted,
        clusterBorder: p.border,
        edgeLabelBackground: p.muted,
        actorBkg: p.surface,
        actorBorder: p.border,
        actorTextColor: p.text,
        signalColor: p.line,
        signalTextColor: p.text,
        noteBkgColor: p.note,
        noteTextColor: p.text,
        noteBorderColor: p.border,
      },
      themeCSS: `.node rect, rect.actor { rx: 9px; ry: 9px; } .nodeLabel, text.actor { font-weight: 500; } .flowchart-link { stroke-width: 1.4px; } .cluster rect { rx: 12px; ry: 12px; } .edgeLabel { font-size: 12px; }`,
    });
    const { svg } = await mermaid.render(id, chart);
    // Parse as HTML, matching insertion into the page. Mermaid output can
    // contain HTML entities that an XML parser would reject.
    const doc = new DOMParser().parseFromString(svg, "text/html");
    const width = Number(
      doc.querySelector("svg")?.getAttribute("viewBox")?.split(/\s+/)[2] ?? 0,
    );
    return { svg, width };
  });
  pending = task.catch(() => undefined);
  return task;
}
