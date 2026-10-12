import { Outlet } from "react-router-dom";
import { Suspense, useState } from "react";

import { LoadingState } from "../ui/Feedback";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";

export default function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="app-shell">
      <Sidebar mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />
      <div className="app-main">
        <Topbar onMenu={() => setMobileOpen(true)} />
        <main className="page-container">
          {/*
            The route pages are lazy-loaded, so this boundary catches the wait for a
            page's chunk. It sits around the outlet rather than around the whole app
            so the sidebar and topbar remain mounted while a page arrives.
          */}
          <Suspense fallback={<LoadingState label="Loading page" />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  );
}
