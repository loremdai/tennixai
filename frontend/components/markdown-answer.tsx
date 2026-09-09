import ReactMarkdown from 'react-markdown'

type MarkdownAnswerProps = {
  content: string
}

export function MarkdownAnswer({ content }: MarkdownAnswerProps) {
  return (
    <div
      className="mt-2 break-words text-sm leading-relaxed text-muted-foreground [&_a]:text-primary [&_a]:underline [&_li]:pl-1 [&_ol]:my-2 [&_ol]:list-decimal [&_ol]:pl-5 [&_p+p]:mt-3 [&_strong]:font-semibold [&_strong]:text-foreground [&_ul]:my-2 [&_ul]:list-disc [&_ul]:pl-5"
    >
      <ReactMarkdown skipHtml>{content}</ReactMarkdown>
    </div>
  )
}
