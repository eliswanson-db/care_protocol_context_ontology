import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { DemoProvider } from "./demo";
import { SettingsProvider } from "./settings";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <DemoProvider>
      <SettingsProvider>
        <App />
      </SettingsProvider>
    </DemoProvider>
  </React.StrictMode>
);
