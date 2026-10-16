import { Link, useRouterState } from '@tanstack/react-router'
import {
  BookA,
  ChartLine,
  CircleHelp,
  Flame,
  House,
  MessagesSquare,
  Monitor,
  Moon,
  Play,
  RefreshCw,
  SlidersHorizontal,
  SpellCheck,
  Strikethrough,
  Sun,
  type LucideIcon,
} from 'lucide-react'
import { useBootstrap } from '@/api/queries'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  SidebarSeparator,
} from '@/components/ui/sidebar'
import { useUpdateFlow } from '@/features/update/use-update-flow'
import { useTheme } from '@/hooks/use-theme'
import type { Theme } from '@/lib/theme'
import { cn } from '@/lib/utils'
import { PencilMark } from './pencil-mark'

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  exact?: boolean
}

const NAV: NavItem[] = [
  { to: '/', label: 'Home', icon: House, exact: true },
  { to: '/mistakes', label: 'Mistakes', icon: Strikethrough },
  { to: '/words', label: 'Words', icon: BookA },
  { to: '/messages', label: 'Messages', icon: MessagesSquare },
  { to: '/check', label: 'Check writing', icon: SpellCheck },
  { to: '/progress', label: 'Progress', icon: ChartLine },
]

const THEMES: { value: Theme; label: string; icon: LucideIcon }[] = [
  { value: 'system', label: 'Same as Windows', icon: Monitor },
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
]

function useIsActive() {
  const path = useRouterState({ select: (s) => s.location.pathname })
  return (item: Pick<NavItem, 'to' | 'exact'>) => (item.exact ? path === item.to : path === item.to || path.startsWith(`${item.to}/`))
}

export function AppSidebar() {
  const { data } = useBootstrap()
  const isActive = useIsActive()
  const counts = data?.counts
  const roundBadge = counts ? (counts.cards_due || (counts.new_cards_ready ? `${counts.new_cards_ready} new` : '')) : ''

  return (
    <Sidebar variant="inset" collapsible="icon">
      <SidebarHeader className="gap-3 pt-3">
        <Link to="/" aria-label="Personal English Tutor, home" className="flex h-11 items-center gap-2.5 rounded-lg px-2 text-ink">
          <PencilMark className="size-[22px] shrink-0 text-pencil" />
          <span className="grid gap-0.5 leading-none group-data-[collapsible=icon]:hidden">
            <span className="text-[11px] font-bold tracking-[0.14em] text-ink-2 uppercase">Personal</span>
            <span className="truncate font-display text-[19px] font-extrabold tracking-tight">English Tutor</span>
          </span>
        </Link>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              size="lg"
              tooltip="Start a round"
              render={<Link to="/practice" search={{ mode: 'cards' }} />}
              className="bg-pencil font-bold text-pencil-ink shadow-e1 hover:bg-pencil-hover hover:text-pencil-ink active:bg-pencil-hover active:text-pencil-ink"
            >
              <Play className="fill-current" aria-hidden />
              <span>Start a round</span>
            </SidebarMenuButton>
            {roundBadge !== '' && roundBadge !== 0 && (
              <SidebarMenuBadge className="bg-pencil-ink/15 text-pencil-ink">{roundBadge}</SidebarMenuBadge>
            )}
          </SidebarMenuItem>
          <UpdateItem />
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarMenu className="gap-1">
            {NAV.map((item) => (
              <SidebarMenuItem key={item.to}>
                <SidebarMenuButton isActive={isActive(item)} tooltip={item.label} render={<Link to={item.to} />} className="h-10 text-[15px]">
                  <item.icon aria-hidden />
                  <span>{item.label}</span>
                </SidebarMenuButton>
                {item.to === '/words' && counts && counts.words_due > 0 && <SidebarMenuBadge>{counts.words_due}</SidebarMenuBadge>}
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="pb-3">
        <StatusLine />
        <SidebarSeparator className="mx-0" />
        <SidebarMenu>
          <ThemeMenu />
          <SidebarMenuItem>
            <SidebarMenuButton isActive={isActive({ to: '/settings' })} tooltip="Settings" render={<Link to="/settings" />}>
              <SlidersHorizontal aria-hidden />
              <span>Settings</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <SidebarMenuButton isActive={isActive({ to: '/help' })} tooltip="How it works" render={<Link to="/help" />}>
              <CircleHelp aria-hidden />
              <span>How it works</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}

function UpdateItem() {
  const flow = useUpdateFlow()
  return (
    <SidebarMenuItem>
      <SidebarMenuButton tooltip="Update my lessons" onClick={flow.open} disabled={flow.busy}
        className="border border-line bg-surface font-semibold hover:bg-surface">
        <RefreshCw className={cn(flow.running && 'animate-spin text-pencil')} aria-hidden />
        <span>{flow.running ? 'Updating lessons…' : 'Update my lessons'}</span>
      </SidebarMenuButton>
      {flow.dialogs}
    </SidebarMenuItem>
  )
}

/** Streak and whether the AI checks can run, in one quiet line. */
function StatusLine() {
  const { data } = useBootstrap()
  if (!data) return null
  const ai = data.ai
  const backup = ai.available && ai.accounts.length > 1 && ai.accounts[0]?.limited_until
  return (
    <div className="grid gap-1 px-2 text-sm text-ink-2 group-data-[collapsible=icon]:hidden">
      <span className="inline-flex items-center gap-1.5">
        <Flame className={cn('size-4', data.streak ? 'text-amber' : 'text-ink-3')} aria-hidden />
        {data.streak ? `${data.streak}-day streak` : 'No streak yet'}
      </span>
      <Link to="/settings" hash="claude" className="inline-flex items-center gap-1.5 hover:text-ink">
        <span className={cn('size-2 rounded-full', ai.available ? (backup ? 'bg-amber' : 'bg-ok') : 'bg-mark')} aria-hidden />
        {ai.available ? (backup ? 'Using backup account' : 'Claude ready') : 'Claude unavailable'}
      </Link>
    </div>
  )
}

function ThemeMenu() {
  const { theme, setTheme } = useTheme()
  const current = THEMES.find((t) => t.value === theme) ?? THEMES[0]!
  return (
    <SidebarMenuItem>
      <DropdownMenu>
        <DropdownMenuTrigger render={<SidebarMenuButton tooltip="Theme" />}>
          <current.icon aria-hidden />
          <span>Theme</span>
        </DropdownMenuTrigger>
        <DropdownMenuContent side="right" align="end" className="min-w-48">
          <DropdownMenuLabel>Theme</DropdownMenuLabel>
          <DropdownMenuRadioGroup value={theme} onValueChange={(v) => setTheme(v as Theme)}>
            {THEMES.map((t) => (
              <DropdownMenuRadioItem key={t.value} value={t.value}>
                <t.icon aria-hidden /> {t.label}
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </SidebarMenuItem>
  )
}
