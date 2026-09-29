'use client'

import type { FormEvent } from 'react'
import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { CircleDot, Menu, Search } from 'lucide-react'

import { Button, buttonVariants } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from '@/components/ui/input-group'
import { cn } from '@/lib/utils'

export type ProductNavKey = 'home' | 'live' | 'schedule' | 'players' | 'markets'

type ProductHeaderProps = {
  active?: ProductNavKey
  marketsHref?: string
  variant?: 'default' | 'markets'
}

const navItems: Array<{ key: ProductNavKey; label: string; href: string }> = [
  { key: 'home', label: '首页', href: '/' },
  { key: 'live', label: '直播', href: '/#live' },
  { key: 'schedule', label: '赛程', href: '/#upcoming' },
  { key: 'players', label: '球员', href: '/players' },
  { key: 'markets', label: '市场', href: '/markets' },
]

export function ProductHeader({
  active = 'home',
  marketsHref = '/markets',
  variant = 'default',
}: ProductHeaderProps) {
  const router = useRouter()
  const [search, setSearch] = useState('')
  const isMarketsHeader = variant === 'markets'
  const resolvedNavItems = navItems.map((item) =>
    item.key === 'markets' ? { ...item, href: marketsHref } : item,
  )

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const value = search.trim()
    if (!value) return
    router.push(`/?q=${encodeURIComponent(value)}#assistant`)
    setSearch('')
  }

  return (
    <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur-xl">
      <div className={cn('mx-auto flex items-center gap-4 px-4 md:px-6', isMarketsHeader ? 'h-14 max-w-7xl' : 'h-16 max-w-7xl')}>
        <Link
          href="/"
          className="flex shrink-0 items-center gap-2.5 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          aria-label="Tennix 首页"
        >
          <span className="flex size-8 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-[0_0_24px_color-mix(in_oklab,var(--primary)_22%,transparent)]">
            <CircleDot aria-hidden="true" className="size-5" />
          </span>
          {isMarketsHeader ? (
            <span className="text-lg font-semibold tracking-tight">TennixAI</span>
          ) : (
            <span className="font-mono text-sm font-bold tracking-[0.14em]">
              TENNIX<span className="text-primary">/AI</span>
            </span>
          )}
        </Link>

        {!isMarketsHeader ? (
          <nav className="hidden h-full items-center gap-1 lg:flex" aria-label="主导航">
            {resolvedNavItems.map((item) => (
              <Link
                key={item.key}
                href={item.href}
                aria-current={active === item.key ? 'page' : undefined}
                className={cn(
                  'relative flex h-full items-center gap-1.5 px-3 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring',
                  active === item.key
                    ? 'text-foreground after:absolute after:inset-x-3 after:bottom-0 after:h-0.5 after:bg-primary'
                    : 'text-muted-foreground hover:text-foreground',
                )}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        ) : null}

        {!isMarketsHeader && active !== 'home' ? (
          <form onSubmit={submitSearch} className="mx-auto hidden w-full max-w-md md:block">
            <label htmlFor="global-search" className="sr-only">
              搜索球员、赛事或询问任何问题
            </label>
            <InputGroup className="h-9 rounded-xl bg-card/70">
              <InputGroupInput
                id="global-search"
                name="global-search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="搜索球员、赛事或提问…"
                autoComplete="off"
              />
              <InputGroupAddon align="inline-start">
                <Search aria-hidden="true" />
              </InputGroupAddon>
            </InputGroup>
            <button type="submit" className="sr-only">搜索</button>
          </form>
        ) : null}

        {isMarketsHeader ? (
          <span className="ml-auto hidden rounded-full border px-3 py-1 text-xs text-muted-foreground sm:inline-flex">
            仅模拟
          </span>
        ) : null}

        <div className={cn('flex shrink-0 items-center gap-1', isMarketsHeader ? 'ml-auto md:ml-0' : 'ml-auto md:ml-0')}>
          {!isMarketsHeader && active !== 'home' ? (
            <Link
              href="/#assistant"
              aria-label="搜索与提问"
              className={cn(buttonVariants({ variant: 'ghost', size: 'icon' }), 'md:hidden')}
            >
              <Search aria-hidden="true" />
            </Link>
          ) : null}

          <DropdownMenu>
            <DropdownMenuTrigger
              render={<Button variant="ghost" size="icon" className={isMarketsHeader ? 'size-11 md:hidden' : 'lg:hidden'} aria-label="打开导航菜单" />}
            >
              <Menu aria-hidden="true" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className={cn('min-w-52', isMarketsHeader ? 'md:hidden' : 'lg:hidden')}>
              <DropdownMenuGroup>
                <DropdownMenuLabel>导航</DropdownMenuLabel>
                {resolvedNavItems.map((item) => (
                  <DropdownMenuItem key={item.key} onClick={() => router.push(item.href)}>
                    {item.label}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuGroup>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  )
}
