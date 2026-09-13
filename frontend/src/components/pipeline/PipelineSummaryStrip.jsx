import { Layers, Briefcase, CalendarCheck, Award } from "lucide-react";
import { deriveSummaryMetrics } from "./pipelineUtils";

export default function PipelineSummaryStrip({ applications = [], activeTab = "all", onSelectTab }) {
  const metrics = deriveSummaryMetrics(applications);

  const cards = [
    {
      id: "all",
      label: "Total Applications",
      count: metrics.total,
      icon: Layers,
      color: "var(--text-primary)",
      targetTab: "all",
    },
    {
      id: "active",
      label: "Active Pipeline",
      count: metrics.active,
      icon: Briefcase,
      color: "var(--accent)",
      targetTab: "active",
    },
    {
      id: "interview",
      label: "Interviews",
      count: metrics.interviews,
      icon: CalendarCheck,
      color: "var(--purple)",
      targetTab: "interview",
    },
    {
      id: "offer",
      label: "Offers Received",
      count: metrics.offers,
      icon: Award,
      color: "var(--success)",
      targetTab: "offer",
    },
  ];

  return (
    <section className="pipeline-summary-strip" aria-label="Pipeline overview summary">
      <div className="pipeline-summary-grid">
        {cards.map((item) => {
          const Icon = item.icon;
          const isSelected = activeTab === item.targetTab;

          return (
            <button
              key={item.id}
              type="button"
              className={`pipeline-summary-card ${isSelected ? "selected" : ""}`}
              onClick={() => onSelectTab && onSelectTab(item.targetTab)}
              aria-label={`${item.label}: ${item.count}`}
            >
              <div className="summary-card-icon-wrap" style={{ color: item.color }}>
                <Icon size={18} aria-hidden="true" />
              </div>
              <div className="summary-card-data">
                <span className="summary-card-count font-mono" style={{ color: item.color }}>
                  {item.count}
                </span>
                <span className="summary-card-label">{item.label}</span>
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}
