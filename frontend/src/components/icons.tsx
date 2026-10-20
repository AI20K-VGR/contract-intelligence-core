import type { CSSProperties } from 'react'

type MaterialIconProps = {
  name: string
  className?: string
  title?: string
  style?: CSSProperties
}

export function MaterialIcon({
  name,
  className,
  title,
  style,
}: MaterialIconProps) {
  return (
    <span
      className={`material-symbols-outlined ${className ?? ''}`}
      aria-hidden
      style={style}
      title={title}
    >
      {name}
    </span>
  )
}
