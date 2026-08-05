import { useId } from 'react'

/* The flag-dot — the signature motif of the whole site.
 *
 * Every city dot wears its country's flag, so a swarm of 73 dots is readable
 * without a legend. These are real SVG (the mockups used CSS gradients as a
 * stand-in), simplified to stay legible at 14px: correct colours, correct
 * layout, canton and cross geometry right, fine detail dropped. */

interface Props {
  cc: string
  size?: number
  className?: string
  /** Decorative next to a visible country name; labelled when standing alone. */
  title?: string
}

function Stripes({ colors, horizontal = true }: { colors: string[]; horizontal?: boolean }) {
  const n = colors.length
  return (
    <>
      {colors.map((c, i) => (
        <rect
          key={i}
          x={horizontal ? 0 : (i * 60) / n}
          y={horizontal ? (i * 60) / n : 0}
          width={horizontal ? 60 : 60 / n}
          height={horizontal ? 60 / n : 60}
          fill={c}
        />
      ))}
    </>
  )
}

/** Nordic cross, offset left as on the real flags. */
function NordicCross({ bg, cross, inner }: { bg: string; cross: string; inner?: string }) {
  return (
    <>
      <rect width="60" height="60" fill={bg} />
      <rect x="17" y="0" width="10" height="60" fill={cross} />
      <rect x="0" y="25" width="60" height="10" fill={cross} />
      {inner && (
        <>
          <rect x="19.5" y="0" width="5" height="60" fill={inner} />
          <rect x="0" y="27.5" width="60" height="5" fill={inner} />
        </>
      )}
    </>
  )
}

function Shapes({ cc }: { cc: string }) {
  switch (cc) {
    case 'US':
      return (
        <>
          <rect width="60" height="60" fill="#fff" />
          {Array.from({ length: 7 }, (_, i) => (
            <rect key={i} y={i * 8.57} width="60" height="4.28" fill="#B22234" />
          ))}
          <rect width="30" height="30" fill="#3C3B6E" />
          {[6, 14, 22].map((y) =>
            [5, 13, 21].map((x) => <circle key={`${x}-${y}`} cx={x} cy={y} r="1.7" fill="#fff" />),
          )}
        </>
      )
    case 'CA':
      return (
        <>
          <rect width="60" height="60" fill="#fff" />
          <rect width="15" height="60" fill="#D80621" />
          <rect x="45" width="15" height="60" fill="#D80621" />
          <path
            d="M30 16l3 7 6-3-2 8 5-1-1 4-8 2 1 3h-3l1-3-8-2-1-4 5 1-2-8 6 3z"
            fill="#D80621"
          />
        </>
      )
    case 'GB':
      return (
        <>
          <rect width="60" height="60" fill="#012169" />
          <path d="M0 0l60 60M60 0L0 60" stroke="#fff" strokeWidth="12" />
          <path d="M0 0l60 60M60 0L0 60" stroke="#C8102F" strokeWidth="6" />
          <path d="M30 0v60M0 30h60" stroke="#fff" strokeWidth="20" />
          <path d="M30 0v60M0 30h60" stroke="#C8102F" strokeWidth="11" />
        </>
      )
    case 'IE':
      return <Stripes colors={['#169B62', '#fff', '#FF883E']} horizontal={false} />
    case 'DE':
      return <Stripes colors={['#1a1a1a', '#DD0000', '#FFCE00']} />
    case 'NL':
      return <Stripes colors={['#AE1C28', '#fff', '#21468B']} />
    case 'IT':
      return <Stripes colors={['#009246', '#fff', '#CE2B37']} horizontal={false} />
    case 'ES':
      return (
        <>
          <rect width="60" height="60" fill="#AA151B" />
          <rect y="15" width="60" height="30" fill="#F1BF00" />
        </>
      )
    case 'SE':
      return <NordicCross bg="#006AA7" cross="#FECC02" />
    case 'DK':
      return <NordicCross bg="#C8102F" cross="#fff" />
    case 'NO':
      return <NordicCross bg="#BA0C2F" cross="#fff" inner="#00205B" />
    case 'FI':
      return <NordicCross bg="#fff" cross="#002F6C" />
    case 'AU':
      return (
        <>
          <rect width="60" height="60" fill="#00205B" />
          <g transform="translate(0,0) scale(0.5)">
            <path d="M0 0l60 60M60 0L0 60" stroke="#fff" strokeWidth="12" />
            <path d="M30 0v60M0 30h60" stroke="#fff" strokeWidth="20" />
            <path d="M30 0v60M0 30h60" stroke="#C8102F" strokeWidth="11" />
          </g>
          <circle cx="15" cy="47" r="3.4" fill="#fff" />
          <circle cx="44" cy="18" r="2.2" fill="#fff" />
          <circle cx="47" cy="34" r="2.2" fill="#fff" />
          <circle cx="41" cy="48" r="2.2" fill="#fff" />
          <circle cx="52" cy="45" r="1.6" fill="#fff" />
        </>
      )
    case 'AE':
      return (
        <>
          <rect width="60" height="60" fill="#fff" />
          <rect width="60" height="20" fill="#00732F" />
          <rect y="40" width="60" height="20" fill="#1a1a1a" />
          <rect width="16" height="60" fill="#EF3340" />
        </>
      )
    case 'QA':
      return (
        <>
          <rect width="60" height="60" fill="#8A1538" />
          <rect width="21" height="60" fill="#fff" />
          <path
            d="M21 0l7 3.75-7 3.75 7 3.75-7 3.75 7 3.75-7 3.75 7 3.75-7 3.75 7 3.75-7 3.75 7 3.75-7 3.75 7 3.75-7 3.75 7 3.75-7 3.75V0z"
            fill="#fff"
          />
        </>
      )
    default:
      return <rect width="60" height="60" fill="var(--surface-sunk)" />
  }
}

export function Flag({ cc, size = 20, className, title }: Props) {
  // Unique per instance. With 73 dots on screen a shared id would make every
  // flag resolve url(#id) to whichever copy mounted first, and unmounting that
  // one would break the rest.
  const id = useId()
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 60 60"
      className={className}
      role={title ? 'img' : 'presentation'}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      style={{
        borderRadius: '50%',
        border: `${Math.max(1, size / 12)}px solid var(--surface)`,
        boxShadow: 'var(--shadow-sm)',
        flex: 'none',
        display: 'block',
      }}
    >
      <defs>
        <clipPath id={id}>
          <circle cx="30" cy="30" r="30" />
        </clipPath>
      </defs>
      <g clipPath={`url(#${id})`}>
        <Shapes cc={cc} />
      </g>
    </svg>
  )
}

/** The two-stage residency bar uses a flag ribbon rather than a dot. */
export function FlagRibbon({ cc, width, height = 12 }: { cc: string; width: number; height?: number }) {
  const id = `rib-${cc}-${width}`
  return (
    <svg width={width} height={height} viewBox="0 0 60 60" preserveAspectRatio="none"
      aria-hidden="true"
      style={{ borderRadius: 'var(--radius-sm)', boxShadow: 'var(--shadow-sm)', flex: 'none', display: 'block' }}>
      <defs>
        <clipPath id={id}><rect width="60" height="60" rx="4" /></clipPath>
      </defs>
      <g clipPath={`url(#${id})`}><Shapes cc={cc} /></g>
    </svg>
  )
}
