'use client'

import { useState } from 'react'
import { SlidersHorizontal, X } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export type PreviewControlField = {
  key: string
  label: string
  value: string
  options: Array<{ value: string; label: string }>
}

function Controls({
  fields,
  onChange,
  stacked = false,
}: {
  fields: PreviewControlField[]
  onChange: (key: string, value: string) => void
  stacked?: boolean
}) {
  return (
    <div className={cn('flex gap-3', stacked ? 'flex-col' : 'flex-wrap items-end')}>
      {fields.map((field) => (
        <label key={field.key} className={cn('flex flex-col gap-1.5', stacked && 'w-full')}>
          <span className="text-xs font-medium text-muted-foreground">{field.label}</span>
          <select
            value={field.value}
            onChange={(event) => onChange(field.key, event.target.value)}
            className="h-11 min-w-36 rounded-lg border border-input bg-background px-3 text-sm text-foreground outline-none transition-shadow focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 md:h-9"
          >
            {field.options.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
      ))}
    </div>
  )
}

export function P3PreviewControls({
  title,
  description,
  fields,
  onChange,
  className,
}: {
  title: string
  description: string
  fields: PreviewControlField[]
  onChange: (key: string, value: string) => void
  className?: string
}) {
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <section className={cn('rounded-xl border bg-card/65 p-3', className)} aria-label={title}>
      <div className="hidden items-center justify-between gap-4 md:flex">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold">{title}</p>
            <Badge variant="outline">演示页面</Badge>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        </div>
        <Controls fields={fields} onChange={onChange} />
      </div>

      <div className="flex items-center justify-between gap-3 md:hidden">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-sm font-semibold">{title}</p>
            <Badge variant="outline">演示</Badge>
          </div>
          <p className="mt-1 truncate text-xs text-muted-foreground">{description}</p>
        </div>
        <Button
          variant="outline"
          size="lg"
          onClick={() => setMobileOpen(true)}
          aria-haspopup="dialog"
          aria-expanded={mobileOpen}
        >
          <SlidersHorizontal data-icon="inline-start" aria-hidden="true" />
          切换状态
        </Button>
      </div>

      {mobileOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-end bg-foreground/25"
          role="presentation"
          onKeyDown={(event) => {
            if (event.key === 'Escape') setMobileOpen(false)
          }}
        >
          <button
            type="button"
            className="absolute inset-0 cursor-default"
            aria-label="关闭状态面板"
            onClick={() => setMobileOpen(false)}
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="p3-preview-drawer-title"
            className="relative z-10 flex max-h-[82dvh] w-full flex-col gap-5 overflow-y-auto rounded-t-2xl bg-card p-5 text-card-foreground shadow-2xl ring-1 ring-foreground/10"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 id="p3-preview-drawer-title" className="text-base font-semibold">{title}</h2>
                <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{description}</p>
              </div>
              <Button variant="ghost" size="icon-lg" onClick={() => setMobileOpen(false)} aria-label="关闭状态面板" autoFocus>
                <X aria-hidden="true" />
              </Button>
            </div>
            <Controls fields={fields} onChange={onChange} stacked />
            <Button size="lg" onClick={() => setMobileOpen(false)}>完成</Button>
          </div>
        </div>
      ) : null}
    </section>
  )
}
