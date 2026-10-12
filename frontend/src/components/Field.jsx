import { useState } from "react";

// Label + icon + input in one place. Extra props (value, onChange, placeholder, ...)
// go straight to the <input>. Password fields get a Show/Hide button.
export default function Field({ id, label, icon, type, ...inputProps }) {
  const [visible, setVisible] = useState(false);
  const isPassword = type === "password";
  const inputType = isPassword && visible ? "text" : type;
  const className = [icon ? "has-icon" : "", isPassword ? "has-toggle" : ""].join(" ").trim();

  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <div className="input-wrap">
        {icon && <span className="input-icon">{icon}</span>}
        <input id={id} type={inputType} className={className} {...inputProps} />
        {isPassword && (
          <button
            type="button"
            className="toggle-visibility"
            onClick={() => setVisible((current) => !current)}
            aria-label={visible ? "Hide password" : "Show password"}
          >
            {visible ? "Hide" : "Show"}
          </button>
        )}
      </div>
    </div>
  );
}
