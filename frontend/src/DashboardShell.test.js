import React from "react";
import ReactDOMServer from "react-dom/server";
import { WorkspaceSidebar } from "./components/dashboard/WorkspaceSidebar";

describe("authenticated dashboard shell", () => {
  test("renders the workspace sidebar without throwing", () => {
    const html = ReactDOMServer.renderToString(
      <WorkspaceSidebar
        t={(key) => key}
        activeMode="single"
        sessionId={null}
        backendUrl=""
        customRulesCount={0}
        onNewDocument={() => {}}
        onToggleMode={() => {}}
        onOpenRulesEditor={() => {}}
        onOpenDevFixtures={() => {}}
      />,
    );

    expect(html).toContain("workspace-sidebar");
    expect(html).toContain("sidebar-dashboard");
  });
});
