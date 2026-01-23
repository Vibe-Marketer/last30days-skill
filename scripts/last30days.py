#!/usr/bin/env python3
"""
last30days - Research a topic from the last 30 days on Reddit + X.

Usage:
    python3 last30days.py <topic> [options]

Options:
    --refresh           Bypass cache and fetch fresh data
    --mock              Use fixtures instead of real API calls
    --emit=MODE         Output mode: compact|json|md|context|path (default: compact)
    --sources=MODE      Source selection: auto|reddit|x|both (default: auto)
    --quick             Faster research with fewer sources (8-12 each)
    --deep              Comprehensive research with more sources (50-70 Reddit, 40-60 X)
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add lib to path
SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

from lib import (
    cache,
    dates,
    dedupe,
    env,
    http,
    models,
    normalize,
    openai_reddit,
    reddit_enrich,
    render,
    schema,
    score,
    xai_x,
)


def load_fixture(name: str) -> dict:
    """Load a fixture file."""
    fixture_path = SCRIPT_DIR.parent / "fixtures" / name
    if fixture_path.exists():
        with open(fixture_path) as f:
            return json.load(f)
    return {}


def run_research(
    topic: str,
    sources: str,
    config: dict,
    selected_models: dict,
    from_date: str,
    to_date: str,
    depth: str = "default",
    mock: bool = False,
) -> tuple:
    """Run the research pipeline.

    Returns:
        Tuple of (reddit_items, x_items, raw_openai, raw_xai, raw_reddit_enriched, reddit_error, x_error)
    """
    reddit_items = []
    x_items = []
    raw_openai = None
    raw_xai = None
    raw_reddit_enriched = []
    reddit_error = None
    x_error = None

    # Reddit search via OpenAI
    if sources in ("both", "reddit"):
        if mock:
            raw_openai = load_fixture("openai_sample.json")
        else:
            try:
                raw_openai = openai_reddit.search_reddit(
                    config["OPENAI_API_KEY"],
                    selected_models["openai"],
                    topic,
                    depth=depth,
                )
            except http.HTTPError as e:
                print(f"[REDDIT ERROR] OpenAI API request failed: {e}", flush=True)
                if e.body:
                    print(f"[REDDIT ERROR] Response body: {e.body[:500]}", flush=True)
                raw_openai = {"error": str(e)}
                reddit_error = f"API error: {e}"
            except Exception as e:
                print(f"[REDDIT ERROR] Unexpected error: {type(e).__name__}: {e}", flush=True)
                raw_openai = {"error": str(e)}
                reddit_error = f"{type(e).__name__}: {e}"

        # Parse response
        reddit_items = openai_reddit.parse_reddit_response(raw_openai)

        # Enrich with real Reddit data
        for i, item in enumerate(reddit_items):
            if mock:
                mock_thread = load_fixture("reddit_thread_sample.json")
                reddit_items[i] = reddit_enrich.enrich_reddit_item(item, mock_thread)
            else:
                reddit_items[i] = reddit_enrich.enrich_reddit_item(item)

            raw_reddit_enriched.append(reddit_items[i])

    # X search via xAI
    if sources in ("both", "x"):
        if mock:
            raw_xai = load_fixture("xai_sample.json")
        else:
            raw_xai = xai_x.search_x(
                config["XAI_API_KEY"],
                selected_models["xai"],
                topic,
                from_date,
                to_date,
                depth=depth,
            )

        # Parse response
        x_items = xai_x.parse_x_response(raw_xai)

    return reddit_items, x_items, raw_openai, raw_xai, raw_reddit_enriched, reddit_error, x_error


def main():
    parser = argparse.ArgumentParser(
        description="Research a topic from the last 30 days on Reddit + X"
    )
    parser.add_argument("topic", nargs="?", help="Topic to research")
    parser.add_argument("--refresh", action="store_true", help="Bypass cache")
    parser.add_argument("--mock", action="store_true", help="Use fixtures")
    parser.add_argument(
        "--emit",
        choices=["compact", "json", "md", "context", "path"],
        default="compact",
        help="Output mode",
    )
    parser.add_argument(
        "--sources",
        choices=["auto", "reddit", "x", "both"],
        default="auto",
        help="Source selection",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Faster research with fewer sources (8-12 each)",
    )
    parser.add_argument(
        "--deep",
        action="store_true",
        help="Comprehensive research with more sources (50-70 Reddit, 40-60 X)",
    )

    args = parser.parse_args()

    # Determine depth
    if args.quick and args.deep:
        print("Error: Cannot use both --quick and --deep", file=sys.stderr)
        sys.exit(1)
    elif args.quick:
        depth = "quick"
    elif args.deep:
        depth = "deep"
    else:
        depth = "default"

    if not args.topic:
        print("Error: Please provide a topic to research.", file=sys.stderr)
        print("Usage: python3 last30days.py <topic> [options]", file=sys.stderr)
        sys.exit(1)

    # Load config
    config = env.get_config()

    # Check available sources
    available = env.get_available_sources(config)
    if available == "none" and not args.mock:
        print("Error: No API keys configured.", file=sys.stderr)
        print("Please add at least one key to ~/.config/last30days/.env:", file=sys.stderr)
        print("  OPENAI_API_KEY=sk-...", file=sys.stderr)
        print("  XAI_API_KEY=xai-...", file=sys.stderr)
        sys.exit(1)

    # Mock mode can work without keys
    if args.mock:
        if args.sources == "auto":
            sources = "both"
        else:
            sources = args.sources
    else:
        # Validate requested sources against available
        sources, error = env.validate_sources(args.sources, available)
        if error:
            print(f"Error: {error}", file=sys.stderr)
            sys.exit(1)

    # Get date range
    from_date, to_date = dates.get_date_range(30)

    # Check cache (unless refresh or mock)
    cache_key = cache.get_cache_key(args.topic, from_date, to_date, f"{sources}:{depth}")
    if not args.refresh and not args.mock:
        cached = cache.load_cache(cache_key)
        if cached:
            # Use cached data
            report = schema.Report.from_dict(cached)
            output_result(report, args.emit)
            return

    # Select models
    if args.mock:
        # Use mock models
        mock_openai_models = load_fixture("models_openai_sample.json").get("data", [])
        mock_xai_models = load_fixture("models_xai_sample.json").get("data", [])
        selected_models = models.get_models(
            {
                "OPENAI_API_KEY": "mock",
                "XAI_API_KEY": "mock",
                **config,
            },
            mock_openai_models,
            mock_xai_models,
        )
    else:
        selected_models = models.get_models(config)

    # Determine mode string
    if sources == "both":
        mode = "both"
    elif sources == "reddit":
        mode = "reddit-only"
    else:
        mode = "x-only"

    # Run research
    reddit_items, x_items, raw_openai, raw_xai, raw_reddit_enriched, reddit_error, x_error = run_research(
        args.topic,
        sources,
        config,
        selected_models,
        from_date,
        to_date,
        depth,
        args.mock,
    )

    # Normalize items
    normalized_reddit = normalize.normalize_reddit_items(reddit_items, from_date, to_date)
    normalized_x = normalize.normalize_x_items(x_items, from_date, to_date)

    # Score items
    scored_reddit = score.score_reddit_items(normalized_reddit)
    scored_x = score.score_x_items(normalized_x)

    # Sort items
    sorted_reddit = score.sort_items(scored_reddit)
    sorted_x = score.sort_items(scored_x)

    # Dedupe items
    deduped_reddit = dedupe.dedupe_reddit(sorted_reddit)
    deduped_x = dedupe.dedupe_x(sorted_x)

    # Create report
    report = schema.create_report(
        args.topic,
        from_date,
        to_date,
        mode,
        selected_models.get("openai"),
        selected_models.get("xai"),
    )
    report.reddit = deduped_reddit
    report.x = deduped_x
    report.reddit_error = reddit_error
    report.x_error = x_error

    # Generate context snippet
    report.context_snippet_md = render.render_context_snippet(report)

    # Write outputs
    render.write_outputs(report, raw_openai, raw_xai, raw_reddit_enriched)

    # Cache the result (if not mock)
    if not args.mock:
        cache.save_cache(cache_key, report.to_dict())

    # Output result
    output_result(report, args.emit)


def output_result(report: schema.Report, emit_mode: str):
    """Output the result based on emit mode."""
    if emit_mode == "compact":
        print(render.render_compact(report))
    elif emit_mode == "json":
        print(json.dumps(report.to_dict(), indent=2))
    elif emit_mode == "md":
        print(render.render_full_report(report))
    elif emit_mode == "context":
        print(report.context_snippet_md)
    elif emit_mode == "path":
        print(render.get_context_path())


if __name__ == "__main__":
    main()
