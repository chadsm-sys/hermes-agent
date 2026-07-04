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

  function fmtUptime(s) {
    if (s == null) return null;
    const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600);
    return d > 0 ? d + "d " + h + "h" : h + "h " + Math.floor((s % 3600) / 60) + "m";
  }

  function fmtAgo(ts) {
    if (ts == null) return "never";
    const s = Math.max(0, Date.now() / 1000 - ts);
    return s < 90 ? Math.round(s) + "s ago" : Math.round(s / 60) + "m ago";
  }

  function metricRow(label, value) {
    return value == null ? null : h("div", { style: { fontSize: "0.8rem", opacity: 0.75 } }, label + ": " + value);
  }

  function NodeCard(n) {
    const live = n.source === "live-read-only";
    const liveness = n.alive === true ? "online" : n.alive === false ? "offline" : "not connected";
    const dot = n.alive === true ? "#2da44e" : n.alive === false ? "#c00" : "#888";
    return h("div", {
      key: n.id,
      style: { border: "1px solid var(--color-border,#444)", borderRadius: 6, padding: "0.75rem" }
    },
      h("div", { style: { fontWeight: 600, display: "flex", alignItems: "center", gap: "0.4rem" } },
        h("span", { style: { width: 8, height: 8, borderRadius: 4, background: dot, display: "inline-block" } }),
        n.label),
      h("div", { style: { fontSize: "0.8rem", opacity: 0.7 } },
        n.role + " \u00b7 " + liveness + (n.breaker_open ? " \u00b7 breaker open" : "")),
      h("div", { style: { fontSize: "0.8rem", opacity: 0.7 } },
        live ? "source: live-read-only" : n.enabled ? "polling" : "disabled (awaiting approval)"),
      metricRow("Hermes", n.version && "v" + n.version),
      metricRow("gateway", n.gateway_state),
      metricRow("uptime", fmtUptime(n.uptime_seconds)),
      metricRow("CPU", n.cpu_percent != null ? n.cpu_percent + "%" : null),
      metricRow("RAM", n.memory_percent != null ? n.memory_percent + "%" : null),
      metricRow("disk", n.disk_percent != null ? n.disk_percent + "%" : null),
      live && metricRow("heartbeat", fmtAgo(n.heartbeat_at)),
      live && metricRow("last poll", fmtAgo(n.last_poll_at)));
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
      }, "READ-ONLY \u2014 Mission Control. Fleet cards for enabled nodes are live (GET-only polls); everything else is local mock data. No controls, no execution."),

      Section("Fleet", StatePanel(fleet, (d) =>
        h("div", { style: { display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(240px,1fr))", gap: "0.75rem" } },
          d.nodes.map(NodeCard)))),

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
