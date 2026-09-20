(() => {
  const root = document.documentElement;
  const button = document.getElementById("themeToggle");
  function setTheme(theme) {
    root.dataset.theme = theme;
    button.textContent = theme === "dark" ? "Light mode ◑" : "Dark mode ◐";
    button.setAttribute(
      "aria-label",
      `Switch to ${theme === "dark" ? "light" : "dark"} theme`,
    );
  }
  try {
    const saved = localStorage.getItem("cg-theme");
    setTheme(saved === "dark" || saved === "light" ? saved : "light");
  } catch {
    setTheme("light");
  }
  button.addEventListener("click", () => {
    setTheme(root.dataset.theme === "dark" ? "light" : "dark");
    try {
      localStorage.setItem("cg-theme", root.dataset.theme);
    } catch {}
  });
  const links = [...document.querySelectorAll(".section-nav a")];
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          links.forEach((link) => {
            if (link.hash === `#${entry.target.id}`)
              link.setAttribute("aria-current", "location");
            else link.removeAttribute("aria-current");
          });
        }
      },
      { rootMargin: "-10% 0px -65% 0px" },
    );
    document
      .querySelectorAll("main section")
      .forEach((section) => observer.observe(section));
  }
  async function renderDiagrams() {
    const diagrams = [...document.querySelectorAll(".mermaid")];
    if (window.mermaid)
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: "strict",
        theme: "base",
        fontFamily: "Arial, sans-serif",
        themeVariables: {
          primaryColor: "#edf5e9",
          primaryTextColor: "#173b2e",
          primaryBorderColor: "#6b957b",
          lineColor: "#6b8272",
          secondaryColor: "#efe9f7",
          tertiaryColor: "#f7f8f3",
          clusterBkg: "#f5f7f1",
          clusterBorder: "#c4d2bf",
          fontSize: "14px",
        },
        flowchart: {
          htmlLabels: false,
          curve: "basis",
          useMaxWidth: true,
          padding: 18,
        },
      });
    for (const [index, element] of diagrams.entries()) {
      const source = element.textContent;
      try {
        if (!window.mermaid) throw new Error("Mermaid unavailable");
        const { svg } = await mermaid.render(`report-diagram-${index}`, source);
        element.innerHTML = svg;
        element.dataset.processed = "true";
        const rendered = element.querySelector("svg");
        rendered.setAttribute("role", "img");
        rendered.setAttribute(
          "aria-label",
          index === 0
            ? "Shared questions flow through either Jev or OpenAI into normalized judgments and the same graph."
            : "Triage flows through a confidence gate into billing, technical, or escalation subgraphs, then finalizes.",
        );
      } catch (error) {
        element.textContent = source;
        const message = document.createElement("p");
        message.className = "diagram-error";
        message.textContent =
          "Diagram could not load. Its readable source is shown below.";
        element.before(message);
        console.error("Diagram rendering failed", error);
      }
    }
  }
  renderDiagrams();
})();
