import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

type MarkdownAnswerProps = {
  content: string
}

export function MarkdownAnswer({ content }: MarkdownAnswerProps) {
  return (
    <div
      data-testid="markdown-answer"
      className="mt-2 break-words text-sm leading-relaxed text-muted-foreground [&_a]:text-primary [&_a]:underline [&_blockquote]:my-3 [&_blockquote]:border-l-2 [&_blockquote]:border-primary/50 [&_blockquote]:pl-3 [&_code]:rounded [&_code]:bg-background/70 [&_code]:px-1 [&_code]:py-0.5 [&_del]:text-muted-foreground/70 [&_del]:line-through [&_h1]:mb-3 [&_h1]:text-lg [&_h1]:font-semibold [&_h2]:mb-2 [&_h2]:mt-4 [&_h2]:text-base [&_h2]:font-semibold [&_h3]:mb-2 [&_h3]:mt-3 [&_h3]:font-semibold [&_hr]:my-4 [&_hr]:border-border [&_input]:mr-1 [&_input]:accent-primary [&_li]:pl-1 [&_ol]:my-2 [&_ol]:list-decimal [&_ol]:pl-5 [&_p+p]:mt-3 [&_pre]:my-3 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-background/80 [&_pre]:p-3 [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_strong]:font-semibold [&_strong]:text-foreground [&_table]:my-3 [&_table]:w-full [&_table]:border-collapse [&_td]:border [&_td]:border-border [&_td]:px-2 [&_td]:py-1 [&_th]:border [&_th]:border-border [&_th]:bg-background/50 [&_th]:px-2 [&_th]:py-1 [&_th]:text-left [&_ul]:my-2 [&_ul]:list-disc [&_ul]:pl-5"
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml>{content}</ReactMarkdown>
    </div>
  )
}
