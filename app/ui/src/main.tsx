
import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./index.css";

const rootEl = document.getElementById("root");

if (!rootEl) {
  const dbg = document.createElement("div");
  dbg.textContent = "UI bootstrap error: #root not found";
  dbg.style.color = "#ff3366";
  document.body.appendChild(dbg);
} else {
  try {
    createRoot(rootEl).render(<App />);
  } catch (err) {
    console.error("UI render failed", err);
    const dbg = document.createElement("pre");
    dbg.textContent = `UI render failed: ${String(err)}`;
    dbg.style.color = "#ff3366";
    dbg.style.padding = "16px";
    document.body.appendChild(dbg);
  }
}
  
