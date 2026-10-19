import { createFileRoute, Outlet } from '@tanstack/react-router'
import { CloudOff } from 'lucide-react'
import { ApiError } from '@/api/client'
import { useBootstrap } from '@/api/queries'
import { SidebarInset, SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar'
import { AppSidebar } from '@/features/shell/app-sidebar'
import { AppMark } from '@/features/shell/app-mark'
import { useLessonUpdates } from '@/features/shell/use-lesson-updates'
import { UpdateBanner } from '@/features/update/update-banner'

// The sidebar layout around every page except practice (which is full screen).
export const Route = createFileRoute('/_app')({
  component: AppLayout,
})

function readSidebarOpen(): boolean {
  return !document.cookie.split('; ').includes('sidebar_state=false')
}

function AppLayout() {
  useLessonUpdates()
  return (
    <SidebarProvider defaultOpen={readSidebarOpen()}>
      <AppSidebar />
      <SidebarInset className="min-h-svh bg-paper md:min-h-[calc(100svh-1rem)]">
        <header className="sticky top-0 z-10 flex h-14 items-center gap-2 border-b bg-paper/90 px-3 backdrop-blur md:hidden">
          <SidebarTrigger className="size-11" aria-label="Open the menu" />
          <AppMark className="size-5 text-pencil" />
          <span className="font-display text-lg font-extrabold tracking-tight">Personal English Tutor</span>
        </header>
        <ServerBanner />
        <UpdateBanner />
        <Outlet />
      </SidebarInset>
    </SidebarProvider>
  )
}

function ServerBanner() {
  const { error } = useBootstrap()
  if (!(error instanceof ApiError && error.offline)) return null
  return (
    <div aria-live="polite" className="m-3 flex items-center gap-3 rounded-lg bg-amber-soft px-4 py-3 text-ink md:m-4">
      <CloudOff className="size-5 shrink-0 text-amber" aria-hidden />
      <p>
        Can&rsquo;t reach the app&rsquo;s server. Start it again with <b>start.cmd</b>; this page reconnects by itself.
      </p>
    </div>
  )
}
