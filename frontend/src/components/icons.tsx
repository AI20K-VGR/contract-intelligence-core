type MaterialIconProps = {
  name: string
  className?: string
  title?: string
}

export function MaterialIcon({ name, className, title }: MaterialIconProps) {
  return (
    <span
      className={`material-symbols-outlined ${className ?? ''}`}
      aria-hidden
      title={title}
    >
      {name}
    </span>
  )
}
