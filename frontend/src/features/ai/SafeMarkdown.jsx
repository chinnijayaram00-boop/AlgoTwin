import { Fragment } from "react";

import { parseMarkdown } from "./markdown";

/**
 * Renders generated insight text from a closed Markdown subset.
 *
 * Every node is rendered as one specific React element with text as text. There is
 * no `dangerouslySetInnerHTML` here and no path to one: `parseMarkdown` can only
 * return the node types this file switches on, and a node it does not recognise
 * falls through to literal text rather than to raw HTML.
 *
 * That matters more than usual for this component, because its input is generated
 * by a model. A model can be induced -- by a problem statement, a code comment, or
 * anything else it was shown -- to emit `<img src=x onerror=...>`. A renderer that
 * accepts HTML would execute that in every learner's browser. This one cannot,
 * whatever the model says.
 *
 * Links are limited to `http`, `https`, and `mailto` by `safeHref` before they get
 * here, and they open with `rel="noreferrer"` so a linked page learns nothing about
 * the deployment.
 */
export default function SafeMarkdown({ text, className = "" }) {
  if (typeof text !== "string" || !text.trim()) return null;
  return <div className={`ai-markdown ${className}`.trim()}>{renderBlocks(parseMarkdown(text))}</div>;
}

function renderBlocks(blocks) {
  return blocks.map((block, index) => <Fragment key={index}>{renderBlock(block)}</Fragment>);
}

function renderBlock(block) {
  switch (block.type) {
    case "heading": {
      // Bounded to h1..h6: the level comes from the model's text, and an
      // unbounded tag name is not something to hand to a component selector.
      const level = Math.min(Math.max(block.level, 1), 6);
      const Heading = `h${level}`;
      return <Heading className="ai-markdown-heading">{renderInline(block.content)}</Heading>;
    }
    case "code":
      return (
        <pre className="ai-markdown-code">
          <code data-language={block.language || undefined}>{block.text}</code>
        </pre>
      );
    case "quote":
      return <blockquote className="ai-markdown-quote">{renderBlocks(block.content)}</blockquote>;
    case "list": {
      const items = block.items.map((item, index) => (
        <li key={index}>{renderInline(item.content)}</li>
      ));
      return block.ordered ? (
        <ol className="ai-markdown-list">{items}</ol>
      ) : (
        <ul className="ai-markdown-list">{items}</ul>
      );
    }
    case "paragraph":
      return <p className="ai-markdown-paragraph">{renderInline(block.content)}</p>;
    default:
      // An unknown block type is shown as its own text rather than dropped, so a
      // parser extension cannot make content disappear without anyone noticing.
      return <p className="ai-markdown-paragraph">{String(block.text ?? "")}</p>;
  }
}

function renderInline(nodes) {
  return nodes.map((node, index) => {
    const key = index;
    switch (node.type) {
      case "code":
        return <code key={key}>{node.text}</code>;
      case "strong":
        return <strong key={key}>{renderInline(node.content)}</strong>;
      case "em":
        return <em key={key}>{renderInline(node.content)}</em>;
      case "link":
        return (
          <a href={node.href} key={key} rel="noreferrer noopener" target="_blank">
            {renderInline(node.content)}
          </a>
        );
      case "break":
        return <br key={key} />;
      case "text":
        return <Fragment key={key}>{node.text}</Fragment>;
      default:
        return <Fragment key={key}>{String(node.text ?? "")}</Fragment>;
    }
  });
}

export { SafeMarkdown };