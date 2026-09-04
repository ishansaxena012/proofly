"""Golden-path deterministic fixture: Sony WH-1000XM6.

IMPORTANT — anti-fabrication policy (docs/ENGINEERING_RULES.md rule 2).

Everything in this module is *synthetic demo material*, not a capture of real
pages, real reviews, real Reddit threads or real YouTube transcripts. To make that
impossible to mistake for live research:

* every URL lives under the reserved, non-resolvable ``.invalid`` TLD on the
  ``fixtures.proofly.invalid`` host, so no fixture URL can ever be confused with a
  real publisher's URL;
* every title is prefixed ``[DEMO FIXTURE]``;
* every author/channel name is obviously a placeholder;
* the report produced from these fixtures carries ``demoMode: true`` plus an
  explicit caveat naming them as fixtures.

The dataset deliberately contains:
  * multiple channels (web / Reddit / YouTube),
  * positive and negative evidence,
  * one genuine, context-dependent conflict (microphone: indoors vs. outdoors),
  * a manufacturer page plus two near-duplicate syndicated copies of its press
    release, so independence clustering has something real to collapse,
  * one single-mention anecdote (hinge creak) that verification must refuse to
    promote into a supported claim,
  * one source that fails to fetch, so graceful channel degradation is exercised.
"""

from __future__ import annotations

from datetime import date

from app.providers.base import (
    RedditComment,
    RedditPost,
    SearchResult,
    WebDocument,
    YouTubeVideo,
)

FIXTURE_HOST = "https://fixtures.proofly.invalid"
DEMO_PREFIX = "[DEMO FIXTURE]"

PRODUCT_QUERY = "Sony WH-1000XM6"

# The fixture's own metadata. The mock LLM may read this because it *is* the
# fixture's data — it is not inventing knowledge about an unknown product.
PRODUCT = {
    "canonical_name": "Sony WH-1000XM6",
    "brand": "Sony",
    "model": "WH-1000XM6",
    "category": "headphones",
}

# The press-release paragraph that the manufacturer page and both syndication
# copies share almost verbatim — the raw material for independence clustering.
_PRESS_RELEASE = (
    "Sony WH-1000XM6 wireless noise cancelling headphones deliver the company's most "
    "advanced noise cancellation to date, powered by the new integrated processor and a "
    "twelve microphone array. The headphones offer up to thirty hours of battery life with "
    "noise cancelling enabled, quick charging that provides three hours of playback from a "
    "three minute charge, and newly developed twelve millimetre drivers tuned for wide "
    "frequency response. Adaptive noise cancelling optimises performance for the wearer, and "
    "precise voice pickup technology isolates the wearer's voice during calls."
)

# ───────────────────────────────── WEB ─────────────────────────────────────

WEB_DOCUMENTS: list[WebDocument] = [
    WebDocument(
        url=f"{FIXTURE_HOST}/web/sony-official/wh-1000xm6-product-page",
        title=f"{DEMO_PREFIX} Manufacturer product page — Sony WH-1000XM6 (official specifications)",
        published_at=date(2025, 5, 14),
        text=(
            f"{_PRESS_RELEASE}\n\n"
            "Specifications. Driver unit: 12 mm dome type. Frequency response: 4 Hz to 40,000 Hz. "
            "Battery life: up to 30 hours with noise cancelling on, up to 40 hours with noise "
            "cancelling off. Charging time: approximately 3.5 hours, with 3 hours of playback from a "
            "3 minute quick charge. Weight: approximately 254 grams. Bluetooth version 5.3 with "
            "support for SBC, AAC, LDAC and LC3 codecs. Multipoint connection to two devices is "
            "supported simultaneously.\n\n"
            "The folding design returns to the series, and the carrying case uses a magnetic closure. "
            "Precise Voice Pickup uses beamforming across the microphone array so that callers hear "
            "the wearer clearly."
        ),
    ),
    WebDocument(
        url=f"{FIXTURE_HOST}/web/audiobench-labs/wh-1000xm6-measured-review",
        title=f"{DEMO_PREFIX} Independent measurement lab review — Sony WH-1000XM6",
        published_at=date(2025, 6, 2),
        text=(
            "We measured the Sony WH-1000XM6 on our test rig over two weeks of daily use. "
            "Sound quality is excellent for the category: the tuning is a mild V shape with a "
            "controlled bass shelf, and our measured frequency response tracks the target curve "
            "within three decibels through the midrange. Compared with the previous generation the "
            "treble is smoother and less prone to sibilance.\n\n"
            "Noise cancellation is the strongest we have measured on a consumer headphone. Broadband "
            "attenuation averaged 32 decibels between 100 Hz and 1 kHz on our rig, which is a "
            "measurable improvement over the previous model. Low frequency rumble on a train or an "
            "aircraft cabin is almost entirely removed.\n\n"
            "Comfort is very good. Clamping force measured 4.1 newtons, which is on the gentle side, "
            "and the 254 gram weight is distributed well enough that we wore them for a full working "
            "day without hot spots.\n\n"
            "Battery life fell slightly short of the manufacturer figure. In our continuous playback "
            "test at 75 decibels with noise cancelling enabled we recorded 28 hours and 20 minutes "
            "rather than the stated 30 hours.\n\n"
            "Microphone and call quality is where our results are mixed. In a quiet indoor room the "
            "microphone is clean and intelligible, and our listening panel rated it above average for "
            "the category. In our wind tunnel test at 15 kilometres per hour the same microphone "
            "degraded badly, with the voice becoming muffled and intermittently unintelligible.\n\n"
            "Value for money is reasonable but not outstanding at the launch price, which is higher "
            "than the previous generation was at launch."
        ),
    ),
    WebDocument(
        url=f"{FIXTURE_HOST}/web/hifi-frontier/wh-1000xm6-long-term-review",
        title=f"{DEMO_PREFIX} Professional long-term review — Sony WH-1000XM6 after three months",
        published_at=date(2025, 8, 19),
        text=(
            "After three months of commuting with the Sony WH-1000XM6 the headline remains the noise "
            "cancellation, which genuinely reduces the fatigue of a daily train commute. The sound "
            "signature is enjoyable and detailed, and the LDAC connection stayed stable on every "
            "device we paired.\n\n"
            "Comfort held up over long sessions. The earpads are deeper than the previous generation, "
            "which helps if you have larger ears, and we had no complaints after four hour flights.\n\n"
            "Battery life in normal mixed use was around 29 hours with noise cancelling on, which "
            "matches the manufacturer claim closely enough that we would not call it optimistic.\n\n"
            "Call quality is the one area where we would temper expectations. Indoors the microphone "
            "is perfectly good and colleagues never asked us to repeat ourselves. Outdoors, "
            "particularly on a windy platform, callers reported that our voice was breaking up and "
            "hard to follow. This is a wind noise problem rather than a general microphone problem.\n\n"
            "The touch control panel is responsive but it becomes noticeably less reliable with cold "
            "fingers or gloves in winter, and we frequently triggered the wrong gesture.\n\n"
            "At this price the competition is real, and the price increase over the previous "
            "generation is hard to ignore."
        ),
    ),
    WebDocument(
        url=f"{FIXTURE_HOST}/web/gadgetwire-syndication/sony-announces-wh-1000xm6",
        title=f"{DEMO_PREFIX} Syndicated press release copy A — Sony announces the WH-1000XM6",
        published_at=date(2025, 5, 14),
        text=(
            "Sony has announced the WH-1000XM6. "
            f"{_PRESS_RELEASE} "
            "Pricing and availability were confirmed by the company at announcement."
        ),
    ),
    WebDocument(
        url=f"{FIXTURE_HOST}/web/techdailyfeed-syndication/sony-wh-1000xm6-announced",
        title=f"{DEMO_PREFIX} Syndicated press release copy B — Sony WH-1000XM6 announced",
        published_at=date(2025, 5, 15),
        text=(
            "Sony announced the WH-1000XM6 this week. "
            f"{_PRESS_RELEASE} "
            "The company confirmed pricing and availability at the announcement."
        ),
    ),
    WebDocument(
        url=f"{FIXTURE_HOST}/web/soundreview-weekly/wh-1000xm6-owner-roundup",
        title=f"{DEMO_PREFIX} Owner feedback roundup — Sony WH-1000XM6",
        published_at=date(2025, 9, 3),
        text=(
            "We collected feedback from owners of the Sony WH-1000XM6 over the summer. The most "
            "common praise by a wide margin is the noise cancellation, followed by comfort on long "
            "flights and the quality of the app's equaliser.\n\n"
            "The most common complaint is the price, which several owners described as hard to "
            "justify against the discounted previous generation. The second most common complaint is "
            "wind noise on calls when walking outdoors.\n\n"
            "A smaller number of owners mentioned that the touch controls misfire when their hands are "
            "cold. Reports of hardware defects were rare in the feedback we collected."
        ),
    ),
]

# One URL that appears in search results but cannot be fetched, so the pipeline
# has to record a FAILED source and carry on.
BROKEN_WEB_URL = f"{FIXTURE_HOST}/web/unavailable-mirror/wh-1000xm6-review"

WEB_SEARCH_RESULTS: list[SearchResult] = [
    SearchResult(
        url=doc.url,
        title=doc.title,
        snippet=doc.text[:180],
        published_at=doc.published_at,
    )
    for doc in WEB_DOCUMENTS
] + [
    SearchResult(
        url=BROKEN_WEB_URL,
        title=f"{DEMO_PREFIX} Unavailable mirror — Sony WH-1000XM6 review",
        snippet="This fixture URL intentionally fails to fetch.",
        published_at=date(2025, 7, 1),
    )
]

# ─────────────────────────────── REDDIT ────────────────────────────────────

REDDIT_POSTS: list[RedditPost] = [
    RedditPost(
        id="fx_reddit_xm6_three_months",
        url=f"{FIXTURE_HOST}/reddit/r/headphones/fx_reddit_xm6_three_months",
        permalink="/r/headphones/comments/fx_reddit_xm6_three_months/",
        subreddit="headphones",
        title=f"{DEMO_PREFIX} Three months with the WH-1000XM6, honest owner notes",
        score=842,
        num_comments=214,
        created_at=date(2025, 8, 27),
        selftext=(
            "I bought the WH-1000XM6 on release and have used them every working day since. The noise "
            "cancelling is the real upgrade, on my underground commute it removes the low rumble "
            "almost completely and I can listen at a lower volume than before.\n\n"
            "Comfort is great for me, I wear glasses and I get no pressure points after a few hours.\n\n"
            "Battery life is around 29 hours for me with noise cancelling on, so basically as "
            "advertised.\n\n"
            "The touch controls are my one real annoyance. In winter with cold fingers they misread "
            "swipes constantly and I end up skipping tracks when I wanted volume."
        ),
        comments=[
            RedditComment(
                id="fx_c_mic_indoor_good",
                author="fixture_user_a",
                score=311,
                body=(
                    "Agreed on all of that. I take calls on these from my home office every day and "
                    "nobody has ever complained about the microphone, it sounds clear indoors."
                ),
            ),
            RedditComment(
                id="fx_c_mic_outdoor_bad",
                author="fixture_user_b",
                score=268,
                body=(
                    "Careful with the mic though. Indoors it is fine but the moment I walk outside on "
                    "a windy day the person on the other end says my voice is breaking up and "
                    "unintelligible. It is specifically wind noise."
                ),
            ),
            RedditComment(
                id="fx_c_price",
                author="fixture_user_c",
                score=140,
                body=(
                    "My only complaint is the price. Great headphones but the previous generation is "
                    "heavily discounted now and gets you most of the way there."
                ),
            ),
        ],
    ),
    RedditPost(
        id="fx_reddit_xm6_mic_question",
        url=f"{FIXTURE_HOST}/reddit/r/headphones/fx_reddit_xm6_mic_question",
        permalink="/r/headphones/comments/fx_reddit_xm6_mic_question/",
        subreddit="headphones",
        title=f"{DEMO_PREFIX} How is the mic on the WH-1000XM6 for work calls?",
        score=317,
        num_comments=96,
        created_at=date(2025, 9, 10),
        selftext=(
            "About to buy a pair mostly for meetings. How is the microphone in practice? I work from "
            "home but I also take calls while walking to the station."
        ),
        comments=[
            RedditComment(
                id="fx_c_mic_meetings_good",
                author="fixture_user_d",
                score=204,
                body=(
                    "For meetings from a quiet room they are genuinely good. Voice pickup is clear and "
                    "my team says I sound better than on my laptop microphone."
                ),
            ),
            RedditComment(
                id="fx_c_mic_walking_bad",
                author="fixture_user_e",
                score=188,
                body=(
                    "Do not rely on them for calls while walking outside. Any breeze and callers say "
                    "the audio is muffled and cutting out. Indoors, no problem at all."
                ),
            ),
            RedditComment(
                id="fx_c_anc_praise",
                author="fixture_user_f",
                score=97,
                body=(
                    "Separately, the noise cancelling on a plane is the best I have used. Flew twelve "
                    "hours and the engine noise basically vanished."
                ),
            ),
        ],
    ),
    RedditPost(
        id="fx_reddit_xm6_hinge",
        url=f"{FIXTURE_HOST}/reddit/r/audiophile/fx_reddit_xm6_hinge",
        permalink="/r/audiophile/comments/fx_reddit_xm6_hinge/",
        subreddit="audiophile",
        title=f"{DEMO_PREFIX} Creaking hinge on my WH-1000XM6 after six months?",
        score=54,
        num_comments=11,
        created_at=date(2025, 9, 1),
        selftext=(
            "My left hinge has started creaking when I fold the headphones. Has anyone else had a "
            "build quality problem like this? Otherwise they have been perfect."
        ),
        comments=[
            RedditComment(
                id="fx_c_hinge_no_issue",
                author="fixture_user_g",
                score=41,
                body=(
                    "Six months here and mine are fine, no creaking at all. Might be worth a warranty "
                    "claim rather than assuming it is a design problem."
                ),
            ),
        ],
    ),
]

# ─────────────────────────────── YOUTUBE ───────────────────────────────────

YOUTUBE_VIDEOS: list[YouTubeVideo] = [
    YouTubeVideo(
        video_id="fx_yt_xm6_review",
        url=f"{FIXTURE_HOST}/youtube/watch/fx_yt_xm6_review",
        title=f"{DEMO_PREFIX} Video review — Sony WH-1000XM6, four weeks later",
        channel_title="Fixture Audio Channel",
        published_at=date(2025, 6, 21),
        description="Synthetic demo transcript used by Proofly's golden-path fixture.",
        transcript=(
            "So I have had the WH-1000XM6 for four weeks now and I want to talk about what actually "
            "changed. The noise cancellation is the headline and it deserves it, on the subway the low "
            "frequency rumble is basically gone and I did not need to raise the volume at all.\n\n"
            "Sound quality out of the box is warm with a bit of extra bass, but it is controlled, and "
            "if you do not like it the app equaliser is genuinely useful.\n\n"
            "Comfort, no complaints, I wore these on a nine hour flight and forgot about them.\n\n"
            "Now the microphone, because this is the part people keep asking about. Here is a sample "
            "recorded in my quiet studio, and honestly it sounds great, it is clean and my voice comes "
            "through clearly. But here is the same microphone recorded outside on a windy afternoon, "
            "and you can hear that the wind completely overwhelms it and my voice is muffled. So the "
            "answer is it depends entirely on where you are.\n\n"
            "Battery, I got about twenty eight and a half hours with noise cancelling on, which is a "
            "bit under the claim but close enough.\n\n"
            "The price is the hard part. This is a meaningful increase over what the previous "
            "generation launched at."
        ),
    ),
    YouTubeVideo(
        video_id="fx_yt_xm6_battery_test",
        url=f"{FIXTURE_HOST}/youtube/watch/fx_yt_xm6_battery_test",
        title=f"{DEMO_PREFIX} Battery drain test — Sony WH-1000XM6",
        channel_title="Fixture Lab Channel",
        published_at=date(2025, 7, 8),
        description="Synthetic demo transcript used by Proofly's golden-path fixture.",
        transcript=(
            "This is a straight battery test. Volume fixed at seventy five decibels, noise cancelling "
            "on, LDAC enabled, playing continuously until shutdown.\n\n"
            "The result was twenty eight hours and ten minutes before the headphones powered off. "
            "With noise cancelling off and AAC instead of LDAC we got thirty nine hours and forty "
            "minutes.\n\n"
            "So the thirty hour claim is achievable only if you are not using LDAC. With LDAC and "
            "noise cancelling you should plan for around twenty eight hours.\n\n"
            "Quick charging worked as advertised, three minutes on the charger gave us just over three "
            "hours of playback."
        ),
    ),
]


def all_fixture_urls() -> set[str]:
    """Every URL this fixture can legitimately produce.

    The evaluation script uses this to prove that no report source URL was
    hallucinated.
    """

    urls = {doc.url for doc in WEB_DOCUMENTS}
    urls.add(BROKEN_WEB_URL)
    urls.update(post.url for post in REDDIT_POSTS)
    urls.update(video.url for video in YOUTUBE_VIDEOS)
    return urls
