import type { ChatWarning } from '@/lib/api/types'

export function ChatWarnings({ warnings }: { warnings: ChatWarning[] }) {
  if (warnings.length === 0) return null

  return (
    <div
      className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-100"
      role="status"
      aria-label="资料可用性提示"
    >
      <p className="font-medium">部分资料暂未提供</p>
      <ul className="mt-1 list-disc space-y-1 pl-4">
        {warnings.map((warning, index) => (
          <li key={`${warning.code}-${index}`}>{warning.message}</li>
        ))}
      </ul>
    </div>
  )
}
