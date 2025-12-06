// Import the ELK layout engine module
import elk from "https://cdn.jsdelivr.net/npm/@mermaid-js/layout-elk@latest/dist/mermaid-layout-elk.esm.min.mjs";

// The theme loads Mermaid.js asynchronously. We need to wait until the
// `window.mermaid` object is available before we can use it.
const observer = setInterval(() => {
  // Check if `window.mermaid` has been loaded
  if (window.mermaid) {
    // Once it's available, stop polling
    clearInterval(observer);

    // Register the ELK layout engine with Mermaid
    window.mermaid.registerLayoutLoaders(elk);

    // Re-render any diagrams that might have already been processed
    // without the ELK layout engine.
    window.mermaid.run({
        nodes: document.querySelectorAll('pre.mermaid > code'),
    });
  }
}, 100); // Check for the object every 100 milliseconds
