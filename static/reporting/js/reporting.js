/* ISI PedagoApp — Reporting JS */
(function () {
  "use strict";

  /* ── Chart.js defaults ────────────────────────────────────── */
  if (window.Chart) {
    Chart.defaults.font.family = "'Barlow', sans-serif";
    Chart.defaults.color = "#64748b";
    Chart.defaults.plugins.legend.display = false;

    /* ── Bar chart helper ─────────────────────────────────────── */
    window.buildBarChart = function (canvasId, labels, data, color) {
      var ctx = document.getElementById(canvasId);
      if (!ctx) return;
      new Chart(ctx, {
        type: "bar",
        data: {
          labels: labels,
          datasets: [{
            data: data,
            backgroundColor: color || "rgba(245,158,11,0.75)",
            borderColor: color || "#f59e0b",
            borderWidth: 1.5,
            borderRadius: 5,
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: {
              beginAtZero: true,
              grid: { color: "#e2e8f0" },
              ticks: { precision: 0 }
            },
            x: { grid: { display: false } }
          }
        }
      });
    };

    /* ── Horizontal fill-rate bar chart ──────────────────────── */
    window.buildHorizontalBar = function (canvasId, labels, data) {
      var ctx = document.getElementById(canvasId);
      if (!ctx) return;
      var colors = data.map(function (v) {
        return v >= 90 ? "#10b981" : v >= 60 ? "#f59e0b" : "#94a3b8";
      });
      new Chart(ctx, {
        type: "bar",
        data: {
          labels: labels,
          datasets: [{
            data: data,
            backgroundColor: colors,
            borderRadius: 4,
          }]
        },
        options: {
          indexAxis: "y",
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: {
              beginAtZero: true,
              max: 100,
              grid: { color: "#e2e8f0" },
              ticks: { callback: function (v) { return v + "%"; } }
            },
            y: { grid: { display: false } }
          }
        }
      });
    };

    /* ── Doughnut chart helper ────────────────────────────────── */
    window.buildDoughnut = function (canvasId, labels, data, colors) {
      var ctx = document.getElementById(canvasId);
      if (!ctx) return;
      new Chart(ctx, {
        type: "doughnut",
        data: {
          labels: labels,
          datasets: [{
            data: data,
            backgroundColor: colors || ["#10b981", "#ef4444", "#94a3b8", "#f59e0b"],
            borderWidth: 0,
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              display: true,
              position: "bottom",
              labels: { boxWidth: 12, padding: 14, font: { size: 12 } }
            }
          },
          cutout: "65%"
        }
      });
    };

    /* ── Line chart helper (monthly trend) ───────────────────── */
    window.buildLineChart = function (canvasId, labels, data, color) {
      var ctx = document.getElementById(canvasId);
      if (!ctx) return;
      color = color || "#f59e0b";
      new Chart(ctx, {
        type: "line",
        data: {
          labels: labels,
          datasets: [{
            data: data,
            borderColor: color,
            backgroundColor: color.replace(")", ", 0.08)").replace("rgb", "rgba"),
            borderWidth: 2,
            pointBackgroundColor: color,
            pointRadius: 4,
            fill: true,
            tension: 0.35,
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: { beginAtZero: true, grid: { color: "#e2e8f0" }, ticks: { precision: 0 } },
            x: { grid: { display: false } }
          }
        }
      });
    };
  }

})();
