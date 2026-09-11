import { Globe2 } from 'lucide-react'

import type { PlayerViewModel } from '@/lib/view-models'

type PlayerCountryProps = {
  player: Pick<PlayerViewModel, 'countryCode' | 'countryName' | 'flagUrl'>
  showCode?: boolean
}

export function PlayerCountry({ player, showCode = false }: PlayerCountryProps) {
  const label = `${player.countryName}${player.countryCode === 'WORLD' ? '（WORLD）' : ''}`

  return (
    <span
      className="inline-flex items-center gap-2"
      title={showCode ? `${player.countryName} · ${player.countryCode}` : player.countryName}
      aria-label={label}
    >
      {player.flagUrl ? (
        <img
          src={player.flagUrl}
          alt={`${player.countryName}国旗`}
          width={20}
          height={14}
          loading="eager"
          className="h-3.5 w-5 rounded-sm object-cover ring-1 ring-border"
        />
      ) : player.countryCode === 'WORLD' ? (
        <Globe2 aria-hidden="true" className="size-4 text-muted-foreground" />
      ) : null}
      {showCode ? <span className="font-mono text-xs text-muted-foreground">{player.countryCode}</span> : null}
    </span>
  )
}
