/**
 * Mission Control v0 — dashboard plugin UI (IIFE, no build step).
 * Renders via the sanctioned SDK (web/src/plugins/sdk.d.ts): host React,
 * fetchJSON with auth handling, shared components. READ-ONLY + MOCK banner
 * is always visible in v0.
 */
(function () {
  const sdk = window.__HERMES_PLUGIN_SDK__;
  const registry = window.__HERMES_PLUGINS__;
  if (!sdk || !registry) return;

  const { React, fetchJSON } = sdk;
  const { useEffect, useState } = sdk.hooks;
  const h = React.createElement;
  const API = "/api/plugins/mission-control";

  function useEndpoint(path) {
    const [state, setState] = useState({ loading: true, error: null, data: null });
    useEffect(() => {
      let live = true;
      fetchJSON(API + path)
        .then((data) => live && setState({ loading: false, error: null, data }))
        .catch((err) => live && setState({ loading: false, error: String(err), data: null }));
      return () => { live = false; };
    }, [path]);
    return state;
  }

  function Section(title, body) {
    return h("div", { style: { marginBottom: "1.5rem" } },
      h("h3", { style: { fontWeight: 600, marginBottom: "0.5rem" } }, title),
      body);
  }

  function StatePanel(s, render) {
    if (s.loading) return h("div", { style: { opacity: 0.6 } }, "Loading\u2026");
    if (s.error) return h("div", { style: { color: "var(--color-destructive, #c00)" } }, "Error: " + s.error);
    if (!s.data) return h("div", { style: { opacity: 0.6 } }, "No data.");
    return render(s.data);
  }

  function MissionControl() {
    const fleet = useEndpoint("/fleet/summary");
    const jobs = useEndpoint("/jobs/summary");
    const approvals = useEndpoint("/approvals/summary");
    const opps = useEndpoint("/opportunities/inbox");

    return h("div", { style: { padding: "1rem", maxWidth: 960 } },
      h("div", {
        style: {
          padding: "0.5rem 0.75rem", marginBottom: "1rem", borderRadius: 4,
          border: "1px solid var(--color-border, #444)",
          background: "var(--color-muted, rgba(255,200,0,0.08))",
          fontSize: "0.85rem"
        }
      }, "READ-ONLY \u00b7 LOCAL MOCK DATA \u2014 Mission Control v0. No remote nodes are contacted."),

      Section("Fleet", StatePanel(fleet, (d) =>
        h("div", { style: { display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(240px,1fr))", gap: "0.75rem" } },
          d.nodes.map((n) => h("div", {
            key: n.id,
            style: { border: "1px solid var(--color-border,#444)", borderRadius: 6, padding: "0.75rem" }
          },
            h("div", { style: { fontWeight: 600 } }, n.label),
            h("div", { style: { fontSize: "0.8rem", opacity: 0.7 } },
              n.role + " \u00b7 " + (n.alive === true ? "alive" : n.alive === false ? "down" : "not connected")),
            h("div", { style: { fontSize: "0.8rem", opacity: 0.7 } },
              n.enabled ? "enabled" : "disabled (awaiting approval)")))))),

      Section("Jobs", StatePanel(jobs, (d) =>
        d.jobs.length === 0 ? h("div", { style: { opacity: 0.6 } }, "No jobs.") :
          h("ul", { style: { fontSize: "0.85rem", lineHeight: 1.7 } },
            d.jobs.map((j, i) => h("li", { key: i },
              "[" + j.state + "] " + j.node + " \u00b7 " + j.kind + " \u00b7 " + j.title))))),

      Section("Approvals", StatePanel(approvals, (d) =>
        d.count === 0 ? h("div", { style: { opacity: 0.6 } }, "Nothing pending.") :
          h("ul", { style: { fontSize: "0.85rem", lineHeight: 1.7 } },
            d.approvals.map((a, i) => h("li", { key: i },
              a.node + " \u00b7 " + a.kind + " \u00b7 " + a.summary))))),

      Section("Opportunities", StatePanel(opps, (d) =>
        d.items.length === 0 ? h("div", { style: { opacity: 0.6 } }, "Inbox empty.") :
          h("ul", { style: { fontSize: "0.85rem", lineHeight: 1.7 } },
            d.items.map((o) => h("li", { key: o.id },
              "(" + Math.round(o.confidence * 100) + "% \u00b7 " + o.tier + " \u00b7 " + o.source + ") " + o.title)))))
    );
  }

  registry.register("mission-control", MissionControl);
})();
