export const site = {
  url: "https://ohkit.wh1isper.top",
  repository: "https://github.com/Wh1isper/ohkit",
  description:
    "An independent Python programming interface for agent harnesses.",
};

export function Brand() {
  return (
    <span className="brand">
      <span className="brand-mark" aria-hidden="true">
        oh
      </span>
      ohkit<span className="brand-label">docs</span>
    </span>
  );
}

export const layoutOptions = {
  nav: { title: <Brand /> },
  githubUrl: site.repository,
  links: [{ text: "Documentation", url: "/getting-started/" }],
};
