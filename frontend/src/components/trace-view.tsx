"use client";
import { useState } from "react";
import { FileText, ExternalLink, Quote } from "lucide-react";
import type { Trace, Source } from "@/lib/types";
import {
  Panel,
  Status,
  Metric,
  Json,
  percent,
  money,
  number,
  date,
  Empty,
} from "./ui";
export function TraceView({ trace }: { trace: Trace }) {
  const [source, setSource] = useState<Source>();
  const [quote, setQuote] = useState<string>();
  const claims = trace.config.claims ?? [];
  return (
    <div className="trace-view">
      <Panel
        title="Answer"
        subtitle={date(trace.created_at)}
        action={<Status value={trace.outcome} />}
      >
        <div className="answer" data-testid="answer">
          {trace.error_code ? (
            <div className="notice error">
              <strong>Query failed · {trace.error_code}</strong>
              <p>
                {trace.config.abstention_reason ||
                  "The provider could not produce a verified answer. Review the trace below."}
              </p>
            </div>
          ) : trace.abstained ? (
            <div className="abstention">
              <Quote size={24} />
              <h3>No evidence-backed answer</h3>
              <p>{trace.config.abstention_reason}</p>
            </div>
          ) : claims.length ? (
            claims.map((claim, index) => (
              <div className="claim" key={index}>
                <p>{claim.text}</p>
                <div className="citation-links">
                  {trace.citations.map((c, i) =>
                    c.claim_index === index ? (
                      <button
                        className="citation"
                        key={i}
                        aria-label={`View citation ${i + 1}`}
                        onClick={() => {
                          setSource(
                            trace.retrieved.find(
                              (s) => s.chunk_id === c.chunk_id,
                            ),
                          );
                          setQuote(c.quote);
                        }}
                      >
                        <FileText size={13} />
                        {i + 1} · {c.valid ? "Quote verified" : "Invalid quote"}
                      </button>
                    ) : null,
                  )}
                </div>
              </div>
            ))
          ) : (
            <p>{trace.answer}</p>
          )}
        </div>
        <div className="answer-foot">
          Source and quote checks verify provenance. Semantic support is
          measured separately in evaluations.
        </div>
      </Panel>
      <div className="metrics compact">
        <Metric label="Latency" value={`${number(trace.latency_ms)} ms`} />
        <Metric
          label="Query cost"
          value={money(trace.cost_usd)}
          detail={
            trace.cost_usd == null
              ? "Provider pricing or usage unavailable"
              : undefined
          }
        />
        <Metric
          label="Tokens"
          value={
            trace.config.usage_complete === false
              ? "Partial usage"
              : `${number(trace.input_tokens)} / ${number(trace.output_tokens)}`
          }
          detail={
            trace.config.usage_complete === false
              ? `Observed input / output: ${number(trace.input_tokens)} / ${number(trace.output_tokens)}. Provider did not report all usage.`
              : "Input / output"
          }
        />
        <Metric
          label="Citation coverage"
          value={percent(trace.config.answer_validation?.citation_coverage)}
          detail="Claims with valid source quotes"
        />
      </div>
      {source && (
        <Panel
          title="Source evidence"
          subtitle={`${source.filename} · page ${source.page} · chunk ${source.ordinal + 1}`}
          action={
            <button
              className="button secondary small"
              onClick={() => setSource(undefined)}
            >
              Close source
            </button>
          }
        >
          <div className="source-body">
            {quote && <blockquote>{quote}</blockquote>}
            <p className="source-content">{source.content}</p>
            <a
              className="text-link"
              href={`/api/documents/${source.document_id}/download`}
            >
              Download source
              <ExternalLink size={15} />
            </a>
          </div>
        </Panel>
      )}
      <Panel
        title="Retrieved context"
        subtitle={`${trace.retrieved.length} unique chunks retrieved · cosine similarity`}
      >
        {trace.retrieved.length ? (
          <div className="retrieved-list">
            {trace.retrieved.map((s, i) => (
              <button
                key={s.chunk_id}
                onClick={() => {
                  setSource(s);
                  setQuote(undefined);
                }}
              >
                <span className="rank">{i + 1}</span>
                <div>
                  <strong>{s.filename}</strong>
                  <small>
                    Page {s.page} · chunk {s.ordinal + 1} · {s.token_count}{" "}
                    tokens
                  </small>
                  <p>
                    {s.content.slice(0, 180)}
                    {s.content.length > 180 ? "…" : ""}
                  </p>
                </div>
                <span className="score">{s.score.toFixed(3)}</span>
              </button>
            ))}
          </div>
        ) : (
          <Empty title="No chunks retrieved">
            No source met this query’s retrieval settings.
          </Empty>
        )}
      </Panel>
      <Panel
        title="Execution trace"
        subtitle={`${trace.tool_calls.length} tool calls · ${trace.config.model} · ${trace.config.prompt_version}`}
      >
        <div className="trace-details">
          {trace.tool_calls.map((t, i) => (
            <details key={t.id}>
              <summary>
                <span>
                  {i + 1}. {t.name}
                </span>
                <Status value={t.status} />
                <small>{t.duration_ms} ms</small>
              </summary>
              <h3>Input</h3>
              <Json value={t.input} />
              <h3>Output</h3>
              <Json value={t.output} />
            </details>
          ))}
          <details>
            <summary>Saved configuration & usage</summary>
            <Json value={trace.config} />
          </details>
          <details>
            <summary>Citation validation details</summary>
            <Json value={trace.citations} />
          </details>
          <p className="small muted">Trace {trace.id}</p>
        </div>
      </Panel>
    </div>
  );
}
