"""Data schemas for last30days skill."""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone


@dataclass
class Engagement:
    """Engagement metrics."""
    # Reddit fields
    score: Optional[int] = None
    num_comments: Optional[int] = None
    upvote_ratio: Optional[float] = None

    # X fields
    likes: Optional[int] = None
    reposts: Optional[int] = None
    replies: Optional[int] = None
    quotes: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {}
        if self.score is not None:
            d['score'] = self.score
        if self.num_comments is not None:
            d['num_comments'] = self.num_comments
        if self.upvote_ratio is not None:
            d['upvote_ratio'] = self.upvote_ratio
        if self.likes is not None:
            d['likes'] = self.likes
        if self.reposts is not None:
            d['reposts'] = self.reposts
        if self.replies is not None:
            d['replies'] = self.replies
        if self.quotes is not None:
            d['quotes'] = self.quotes
        return d if d else None


@dataclass
class Comment:
    """Reddit comment."""
    score: int
    date: Optional[str]
    author: str
    excerpt: str
    url: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'score': self.score,
            'date': self.date,
            'author': self.author,
            'excerpt': self.excerpt,
            'url': self.url,
        }


@dataclass
class SubScores:
    """Component scores."""
    relevance: int = 0
    recency: int = 0
    engagement: int = 0

    def to_dict(self) -> Dict[str, int]:
        return {
            'relevance': self.relevance,
            'recency': self.recency,
            'engagement': self.engagement,
        }


@dataclass
class RedditItem:
    """Normalized Reddit item."""
    id: str
    title: str
    url: str
    subreddit: str
    date: Optional[str] = None
    date_confidence: str = "low"
    engagement: Optional[Engagement] = None
    top_comments: List[Comment] = field(default_factory=list)
    comment_insights: List[str] = field(default_factory=list)
    relevance: float = 0.5
    why_relevant: str = ""
    subs: SubScores = field(default_factory=SubScores)
    score: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'title': self.title,
            'url': self.url,
            'subreddit': self.subreddit,
            'date': self.date,
            'date_confidence': self.date_confidence,
            'engagement': self.engagement.to_dict() if self.engagement else None,
            'top_comments': [c.to_dict() for c in self.top_comments],
            'comment_insights': self.comment_insights,
            'relevance': self.relevance,
            'why_relevant': self.why_relevant,
            'subs': self.subs.to_dict(),
            'score': self.score,
        }


@dataclass
class XItem:
    """Normalized X item."""
    id: str
    text: str
    url: str
    author_handle: str
    date: Optional[str] = None
    date_confidence: str = "low"
    engagement: Optional[Engagement] = None
    relevance: float = 0.5
    why_relevant: str = ""
    subs: SubScores = field(default_factory=SubScores)
    score: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'text': self.text,
            'url': self.url,
            'author_handle': self.author_handle,
            'date': self.date,
            'date_confidence': self.date_confidence,
            'engagement': self.engagement.to_dict() if self.engagement else None,
            'relevance': self.relevance,
            'why_relevant': self.why_relevant,
            'subs': self.subs.to_dict(),
            'score': self.score,
        }


@dataclass
class Report:
    """Full research report."""
    topic: str
    range_from: str
    range_to: str
    generated_at: str
    mode: str  # 'reddit-only', 'x-only', 'both'
    openai_model_used: Optional[str] = None
    xai_model_used: Optional[str] = None
    reddit: List[RedditItem] = field(default_factory=list)
    x: List[XItem] = field(default_factory=list)
    best_practices: List[str] = field(default_factory=list)
    prompt_pack: List[str] = field(default_factory=list)
    context_snippet_md: str = ""
    # Status tracking
    reddit_error: Optional[str] = None
    x_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            'topic': self.topic,
            'range': {
                'from': self.range_from,
                'to': self.range_to,
            },
            'generated_at': self.generated_at,
            'mode': self.mode,
            'openai_model_used': self.openai_model_used,
            'xai_model_used': self.xai_model_used,
            'reddit': [r.to_dict() for r in self.reddit],
            'x': [x.to_dict() for x in self.x],
            'best_practices': self.best_practices,
            'prompt_pack': self.prompt_pack,
            'context_snippet_md': self.context_snippet_md,
        }
        if self.reddit_error:
            d['reddit_error'] = self.reddit_error
        if self.x_error:
            d['x_error'] = self.x_error
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Report":
        """Create Report from serialized dict (handles cache format)."""
        # Handle range field conversion
        range_data = data.get('range', {})
        range_from = range_data.get('from', data.get('range_from', ''))
        range_to = range_data.get('to', data.get('range_to', ''))

        # Reconstruct Reddit items
        reddit_items = []
        for r in data.get('reddit', []):
            eng = None
            if r.get('engagement'):
                eng = Engagement(**r['engagement'])
            comments = [Comment(**c) for c in r.get('top_comments', [])]
            subs = SubScores(**r.get('subs', {})) if r.get('subs') else SubScores()
            reddit_items.append(RedditItem(
                id=r['id'],
                title=r['title'],
                url=r['url'],
                subreddit=r['subreddit'],
                date=r.get('date'),
                date_confidence=r.get('date_confidence', 'low'),
                engagement=eng,
                top_comments=comments,
                comment_insights=r.get('comment_insights', []),
                relevance=r.get('relevance', 0.5),
                why_relevant=r.get('why_relevant', ''),
                subs=subs,
                score=r.get('score', 0),
            ))

        # Reconstruct X items
        x_items = []
        for x in data.get('x', []):
            eng = None
            if x.get('engagement'):
                eng = Engagement(**x['engagement'])
            subs = SubScores(**x.get('subs', {})) if x.get('subs') else SubScores()
            x_items.append(XItem(
                id=x['id'],
                text=x['text'],
                url=x['url'],
                author_handle=x['author_handle'],
                date=x.get('date'),
                date_confidence=x.get('date_confidence', 'low'),
                engagement=eng,
                relevance=x.get('relevance', 0.5),
                why_relevant=x.get('why_relevant', ''),
                subs=subs,
                score=x.get('score', 0),
            ))

        return cls(
            topic=data['topic'],
            range_from=range_from,
            range_to=range_to,
            generated_at=data['generated_at'],
            mode=data['mode'],
            openai_model_used=data.get('openai_model_used'),
            xai_model_used=data.get('xai_model_used'),
            reddit=reddit_items,
            x=x_items,
            best_practices=data.get('best_practices', []),
            prompt_pack=data.get('prompt_pack', []),
            context_snippet_md=data.get('context_snippet_md', ''),
            reddit_error=data.get('reddit_error'),
            x_error=data.get('x_error'),
        )


def create_report(
    topic: str,
    from_date: str,
    to_date: str,
    mode: str,
    openai_model: Optional[str] = None,
    xai_model: Optional[str] = None,
) -> Report:
    """Create a new report with metadata."""
    return Report(
        topic=topic,
        range_from=from_date,
        range_to=to_date,
        generated_at=datetime.now(timezone.utc).isoformat(),
        mode=mode,
        openai_model_used=openai_model,
        xai_model_used=xai_model,
    )
