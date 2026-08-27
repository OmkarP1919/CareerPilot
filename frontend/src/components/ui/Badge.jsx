export default function Badge({ variant = "default", children, className = "" }) {
  const classes = [
    "badge",
    variant === "primary" && "badge-primary",
    variant === "success" && "badge-success",
    variant === "warning" && "badge-warning",
    variant === "danger" && "badge-danger",
    variant === "info" && "badge-info",
    variant === "outline" && "badge-outline",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return <span className={classes}>{children}</span>;
}
