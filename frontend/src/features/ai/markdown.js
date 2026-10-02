/**
 * A deliberately small Markdown parser for generated insight text.
 *
 * This module is pure: it turns a string into a tree of plain objects and never
 * touches React. The component that renders the tree lives in `SafeMarkdown.jsx`.
 * Keeping the split means the parser can be tested exhaustively without a DOM, and
 * that nothing in this file can reach for `dangerouslySetInnerHTML`.
 *
 * ## Why not a Markdown library
 *
 * Generated text is the one piece of content in this application that arrives from
 * outside a developer's control and is then shown to other people. A full Markdown
 * renderer accepts raw HTML by default, which means a model that emitted a tag --
 * or a prompt-injected model that was *told* to emit one -- would be one render
 * away from script execution in every learner's browser. The usual fix is a
 * sanitiser, which is a second parser to get right and a permanent source of
 * bypasses.
 *
 * The subset below removes the problem instead of managing it. Every node this
 * parser can produce maps to one specific React element with no `children`
 * injection, no `style`, and no `dangerouslySetInnerHTML`. Anything it does not
 * recognise becomes literal text. There is no path from a model response to an
 * attribute the browser will interpret as markup.
 *
 * ## What is supported
 *
 * ATX headings (`#`..`######`), fenced code blocks, blockquotes, unordered lists
 * (`-`, `*`, `+`), ordered lists, paragraphs, and hard line breaks. Inline: code
 * spans, bold, italics, and links.
 *
 * ## What is not, and why that is fine
 *
 * Images, raw HTML, tables, nested lists, setext headings, and reference-style
 * links are all absent. None are things the prompts ask a model for, and every one
 * of them is a place where "render it approximately" would mean "render it in a way
 * that can lie". Unsupported syntax degrades to readable text.
 */

/** The longest single line kept. A model that returns one enormous line is not to
 * be allowed to produce an unbounded DOM. */
const MAX_BLOCK_LENGTH = 20_000;

/** The deepest list nesting rendered. Beyond this, further items are flattened
 * into their parent. Prevents a pathological input producing a deep tree. */
const MAX_LIST_DEPTH = 4;

/** Blocks are capped so a runaway response cannot build an unbounded tree. */
const MAX_BLOCKS = 500;

/** A link target. Anything else renders as plain text. */
const SAFE_LINK_SCHEMES = new Set(["http:", "https:", "mailto:"]);

/**
 * A safe URL, or `null`.
 *
 * The dangerous schemes are `javascript:`, `data:`, and `vbscript:` -- all of which
 * execute when placed in an `href`. They are rejected by scheme allow-list rather
 * than by block-list, because a block-list is defeated by every scheme nobody
 * thought of. A relative URL is rejected too: the API has no routes that would make
 * one meaningful, and a link that leaves the deployment is a worse default than a
 * link that does nothing.
 */
export function safeHref(url) {
  if (typeof url !== "string") return null;
  const trimmed = url.trim();
  if (!trimmed || trimmed.length > 2_048) return null;
  let parsed;
  try {
    parsed = new URL(trimmed);
  } catch {
    return null;
  }
  return SAFE_LINK_SCHEMES.has(parsed.protocol) ? trimmed : null;
}

/**
 * Parse a Markdown document into a tree of blocks.
 *
 * Block types: `heading`, `paragraph`, `code`, `quote`, `list`. Inline content is
 * an array of `{ type, text, ... }` nodes; `text` nodes carry the literal string
 * and every other node type is rendered by exactly one function in the component.
 */
export function parseMarkdown(source) {
  if (typeof source !== "string" || !source.trim()) return [];

  const lines = source.replace(/\r\n?/g, "\n").split("\n");
  const blocks = [];

  for (let index = 0; index < lines.length && blocks.length < MAX_BLOCKS; index += 1) {
    const line = lines[index];

    if (!line.trim()) continue;

    const fence = /^```+\s*([\w+-]*)\s*$/.exec(line.trim());
    if (fence) {
      const language = fence[1] || "";
      const body = [];
      index += 1;
      while (index < lines.length && !/^```+\s*$/.test(lines[index].trim())) {
        body.push(lines[index]);
        index += 1;
      }
      blocks.push({ type: "code", language, text: body.join("\n").slice(0, MAX_BLOCK_LENGTH) });
      continue;
    }

    const heading = /^(#{1,6})\s+(.*)$/.exec(line);
    if (heading) {
      blocks.push({
        type: "heading",
        level: heading[1].length,
        content: parseInline(heading[2].slice(0, MAX_BLOCK_LENGTH)),
      });
      continue;
    }

    if (/^>\s?/.test(line)) {
      const body = [];
      while (index < lines.length && /^>\s?/.test(lines[index])) {
        body.push(lines[index].replace(/^>\s?/, ""));
        index += 1;
      }
      index -= 1;
      blocks.push({ type: "quote", content: parseBlocks(body.join("\n"), MAX_LIST_DEPTH) });
      continue;
    }

    if (isListItem(line)) {
      const [list, consumed] = collectList(lines, index);
      blocks.push(list);
      index = consumed - 1;
      continue;
    }

    // A paragraph runs until a blank line or the start of another block. Parsed
    // eagerly so the loop's index advance is a single step.
    const body = [];
    while (index < lines.length && lines[index].trim() && !startsBlock(lines[index])) {
      body.push(lines[index]);
      index += 1;
    }
    index -= 1;
    if (body.length) {
      blocks.push({ type: "paragraph", content: parseInline(body.join("\n").slice(0, MAX_BLOCK_LENGTH)) });
    }
  }

  return blocks;
}

/**
 * Parse nested blocks. Only used for blockquote bodies, where the content is
 * itself a small document.
 */
function parseBlocks(source, depth) {
  if (depth <= 0) return [{ type: "paragraph", content: parseInline(source.slice(0, MAX_BLOCK_LENGTH)) }];
  return parseMarkdown(source);
}

function isListItem(line) {
  return /^\s*([-*+]|\d{1,9}[.)])\s+/.test(line);
}

function startsBlock(line) {
  return (
    /^\s*([-*+]|\d{1,9}[.)])\s+/.test(line) ||
    /^>\s?/.test(line) ||
    /^```/.test(line.trim()) ||
    /^(#{1,6})\s+/.test(line)
  );
}

/**
 * Consume one list, including any items nested under it.
 *
 * Returns the list block and the index of the first line *after* it, so the
 * caller's loop can continue from there. Nesting is bounded: an item indented past
 * {@link MAX_LIST_DEPTH} stays in its parent rather than becoming a deeper tree,
 * which is enough for a model that indents for decoration and not enough to
 * exhaust a renderer.
 */
function collectList(lines, start) {
  const first = /^\s*([-*+]|\d{1,9}[.)])\s+/.exec(lines[start]);
  const ordered = /\d/.test(first[1]);
  const baseIndent = first[1].length + lines[start].indexOf(first[1]);
  const items = [];
  let index = start;

  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      // A blank line ends the list unless the next line is indented further,
      // which is how a two-paragraph item is written.
      const following = lines[index + 1];
      if (!following || !following.trim() || indentOf(following) <= baseIndent) break;
      index += 1;
      continue;
    }

    const match = /^\s*([-*+]|\d{1,9}[.)])\s+(.*)$/.exec(line);
    if (match && indentOf(line) === baseIndent) {
      items.push([]);
      index += 1;
      continue;
    }
    if (!match && indentOf(line) > baseIndent && items.length) {
      // A continuation line. Hard break when it ends with two spaces, which is the
      // one Markdown construct with a visual meaning worth keeping.
      const text = line.trim();
      items[items.length - 1].push(text.endsWith("  ") ? { type: "text", text: `${text.trim()}`, break: true } : { type: "text", text });
      index += 1;
      continue;
    }
    break;
  }

  const listItems = items.map((parts) => ({
    content: parseInline(joinItem(parts).slice(0, MAX_BLOCK_LENGTH)),
  }));

  return [{ type: "list", ordered, items: listItems }, index];
}

function indentOf(line) {
  return line.length - line.trimStart().length;
}

function joinItem(parts) {
  return parts
    .map((part) => (part.break ? `${part.text}\n` : part.text))
    .join(" ")
    .replace(/\n{3,}/g, "\n\n");
}

/**
 * Inline spans: code, bold, italics, links, hard breaks.
 *
 * Parsed by a single left-to-right scan rather than by successive regular
 * expression replacements. That ordering is the reason this is correct: code spans
 * are extracted first and their contents removed from the working string, so
 * `**` inside a code span is code rather than bold, and a URL containing
 * underscores is not turned into italics. A replacement-based parser gets this
 * backwards and silently mangles exactly the content a model is most likely to
 * quote -- a variable name, a command line, a path.
 */
export function parseInline(source) {
  if (typeof source !== "string") return [];
  if (!source) return [];

  const nodes = [];
  const pattern = /(`+)([^`]|[^`][\s\S]*?[^`])\1|(\*\*|__)(?=\S)([\s\S]*?\S)\3|(\*|_)(?=\S)([\s\S]*?\S)\5|\[([^\]\n]+)\]\(([^)\s]+)(?:\s+"[^"]*")?\)|(\S{2,})\n/g;
  let cursor = 0;
  let match = pattern.exec(source);

  while (match) {
    if (match.index > cursor) {
      nodes.push({ type: "text", text: source.slice(cursor, match.index) });
    }

    const [whole, , code, , strong, , em, label, href] = match;

    if (code !== undefined) {
      nodes.push({ type: "code", text: code.replace(/^ | $/g, "") });
    } else if (strong !== undefined) {
      nodes.push({ type: "strong", content: parseInline(strong) });
    } else if (em !== undefined) {
      nodes.push({ type: "em", content: parseInline(em) });
    } else if (label !== undefined) {
      const safe = safeHref(href);
      // An unsafe or relative target is shown, not linked. Silently dropping the
      // text would hide what the model actually said; making it a link would make
      // the platform act on it.
      nodes.push(safe ? { type: "link", href: safe, content: parseInline(label) } : { type: "text", text: label });
    } else {
      // A hard break: two spaces or a trailing backslash before a newline.
      nodes.push({ type: "break" });
      void whole;
    }

    cursor = match.index + whole.length;
    match = pattern.exec(source);
  }

  if (cursor < source.length) {
    nodes.push({ type: "text", text: source.slice(cursor) });
  }

  return nodes;
}

/** Strip every inline marker, for a title or a plain-text summary. */
export function markdownToText(source) {
  if (typeof source !== "string") return "";
  return source
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`([^`]*)`/g, "$1")
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/(\*\*|__)(.*?)\1/g, "$2")
    .replace(/(\*|_)(.*?)\1/g, "$2")
    .replace(/^\s{0,3}#{1,6}\s+/gm, "")
    .replace(/^\s{0,3}>\s?/gm, "")
    .replace(/^\s*([-*+]|\d{1,9}[.)])\s+/gm, "")
    .replace(/\s+/g, " ")
    .trim();
}