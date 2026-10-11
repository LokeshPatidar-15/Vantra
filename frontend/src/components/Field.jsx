// Label + icon + input in one place. Any extra props (type, value, onChange,
// placeholder, ...) are passed straight to the <input>.
export default function Field({ id, label, icon, ...inputProps }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <div className="input-wrap">
        {icon && <span className="input-icon">{icon}</span>}
        <input id={id} className={icon ? "has-icon" : ""} {...inputProps} />
      </div>
    </div>
  );
}
