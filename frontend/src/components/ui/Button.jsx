import { forwardRef } from "react";

const Button = forwardRef(function Button(
  {
    variant = "primary",
    size = "default",
    block = false,
    loading = false,
    disabled = false,
    icon: Icon,
    children,
    className = "",
    ...props
  },
  ref
) {
  const classes = [
    "btn",
    variant === "primary" && "btn-primary",
    variant === "secondary" && "btn-secondary",
    variant === "outline" && "btn-outline",
    variant === "ghost" && "btn-ghost",
    variant === "danger" && "btn-danger",
    variant === "google" && "btn-google",
    size === "sm" && "btn-sm",
    size === "lg" && "btn-lg",
    block && "btn-block",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      ref={ref}
      className={classes}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <span className="spinner-inline" />
      ) : Icon ? (
        <Icon size={size === "sm" ? 14 : 16} />
      ) : null}
      {children}
    </button>
  );
});

export default Button;
