import type { ChatWarning } from '@/lib/api/types'

export function ChatWarnings({ warnings }: { warnings: ChatWarning[] }) {
  if (warnings.length === 0) return null

  const hasDataAvailabilityWarning = warnings.some(
    (warning) => !warning.code.startsWith('llm_response_'),
  )

  return (
    <div
      className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-100"
      role="status"
      aria-label="资料可用性提示"
    >
      <p className="font-medium">
        {hasDataAvailabilityWarning ? '部分资料暂未提供' : '回答质量提示'}
      </p>
      <ul className="mt-1 list-disc space-y-1 pl-4">
        {warnings.map((warning, index) => (
          <li key={`${warning.code}-${index}`}>{warning.message}</li>
        ))}
      </ul>
    </div>
  )
}
