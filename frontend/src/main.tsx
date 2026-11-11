/** React entry: RTL root, AuthProvider, BrowserRouter, App. */
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthProvider } from "./lib/auth";
import "./styles/global.css";

// 02/04: RTL + Persian lang on the document root.
document.documentElement.setAttribute("dir", "rtl");
document.documentElement.setAttribute("lang", "fa");

const rootEl = document.getElementById("root");
if (!rootEl) throw new Error("#root element not found");

ReactDOM.createRoot(rootEl).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
