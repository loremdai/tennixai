'use client'

import type { FormEvent } from 'react'
import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import {
  Bell,
  CircleDot,
  HelpCircle,
  LogOut,
  Menu,
  Search,
  SlidersHorizontal,
  UserRound,
} from 'lucide-react'

import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button, buttonVariants } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
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
}

const navItems: Array<{ key: ProductNavKey; label: string; href: string; beta?: boolean }> = [
  { key: 'home', label: '首页', href: '/' },
  { key: 'live', label: '直播', href: '/#live' },
  { key: 'schedule', label: '赛程', href: '/#upcoming' },
  { key: 'players', label: '球员', href: '/players' },
  { key: 'markets', label: '市场', href: '/#markets', beta: true },
]

export function ProductHeader({ active = 'home' }: ProductHeaderProps) {
  const router = useRouter()
  const [search, setSearch] = useState('')
  const [hasNotification, setHasNotification] = useState(true)

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const value = search.trim()
    if (!value) return
    router.push(`/?q=${encodeURIComponent(value)}#assistant`)
    setSearch('')
  }

  return (
    <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-4 px-4 md:px-6">
        <Link
          href="/"
          className="flex shrink-0 items-center gap-2.5 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          aria-label="Tennix 首页"
        >
          <span className="flex size-8 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-[0_0_24px_color-mix(in_oklab,var(--primary)_22%,transparent)]">
            <CircleDot aria-hidden="true" className="size-5" />
          </span>
          <span className="font-mono text-sm font-bold tracking-[0.14em]">
            TENNIX<span className="text-primary">/AI</span>
          </span>
        </Link>

        <nav className="hidden h-full items-center gap-1 lg:flex" aria-label="主导航">
          {navItems.map((item) => (
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
              {item.beta ? (
                <span className="rounded-full bg-premium/15 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-premium">
                  BETA
                </span>
              ) : null}
            </Link>
          ))}
        </nav>

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
              placeholder="搜索球员、赛事或询问任何问题…"
              autoComplete="off"
            />
            <InputGroupAddon align="inline-start">
              <Search aria-hidden="true" />
            </InputGroupAddon>
          </InputGroup>
          <button type="submit" className="sr-only">搜索</button>
        </form>

        <div className="ml-auto flex shrink-0 items-center gap-1 md:ml-0">
          <Button
            variant="ghost"
            size="icon"
            aria-label={hasNotification ? '查看 1 条新通知' : '查看通知'}
            onClick={() => setHasNotification(false)}
            className="relative hidden sm:inline-flex"
          >
            <Bell aria-hidden="true" />
            {hasNotification ? (
              <span className="absolute right-1.5 top-1.5 size-1.5 rounded-full bg-live ring-2 ring-background" aria-hidden="true" />
            ) : null}
          </Button>

          <Button variant="ghost" size="icon" aria-label="打开显示设置" className="hidden sm:inline-flex">
            <SlidersHorizontal aria-hidden="true" />
          </Button>

          <Link
            href="/#assistant"
            aria-label="搜索与询问"
            className={cn(buttonVariants({ variant: 'ghost', size: 'icon' }), 'md:hidden')}
          >
            <Search aria-hidden="true" />
          </Link>

          <DropdownMenu>
            <DropdownMenuTrigger
              render={<Button variant="ghost" size="icon-lg" aria-label="打开用户菜单" />}
            >
              <Avatar size="sm">
                <AvatarFallback>ET</AvatarFallback>
              </Avatar>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="min-w-52">
              <DropdownMenuGroup>
                <DropdownMenuLabel>Etienne · 本地时间</DropdownMenuLabel>
                <DropdownMenuItem onClick={() => router.push('/#players')}>
                  <UserRound aria-hidden="true" />
                  已关注 4 位球员
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => router.push('/#assistant')}>
                  <HelpCircle aria-hidden="true" />
                  询问 Tennix
                </DropdownMenuItem>
              </DropdownMenuGroup>
              <DropdownMenuSeparator />
              <DropdownMenuGroup>
                <DropdownMenuItem>
                  <LogOut aria-hidden="true" />
                  退出登录
                </DropdownMenuItem>
              </DropdownMenuGroup>
            </DropdownMenuContent>
          </DropdownMenu>

          <DropdownMenu>
            <DropdownMenuTrigger
              render={<Button variant="ghost" size="icon" className="lg:hidden" aria-label="打开导航菜单" />}
            >
              <Menu aria-hidden="true" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="min-w-52 lg:hidden">
              <DropdownMenuGroup>
                <DropdownMenuLabel>导航</DropdownMenuLabel>
                {navItems.map((item) => (
                  <DropdownMenuItem key={item.key} onClick={() => router.push(item.href)}>
                    <span>{item.label}</span>
                    {item.beta ? <Badge variant="outline">BETA</Badge> : null}
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
