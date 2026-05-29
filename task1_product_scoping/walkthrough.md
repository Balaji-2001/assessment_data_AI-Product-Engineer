# Walkthrough: How I Thought Through This

*This is the written version of the walkthrough. It's meant to be read as me talking through my thinking, not as a formal document.*

---

## Where I Started

When I first read the brief, I almost immediately started thinking about dashboards. That's the obvious answer to "how is our marketing performing?" — build a dashboard, right? Connect all the tools, put some charts on a screen, done.

I sat with that for a bit and decided it was the wrong answer for this specific problem.

The problem isn't that the team lacks visibility into their data. It's that producing a coherent answer to a specific question is manual, slow, and dependent on the wrong people. A full analytics dashboard doesn't fix that — it just gives you another tool to dig through. You still have to interpret it. You still have to write the summary. You still have to know which numbers matter.

So I shifted my thinking. The question isn't "what should the dashboard show?" It's "what does the answer to the question actually look like, and how do we make that answer consistently available?"

That reframe changed everything about how I scoped this.

---

## The Decision That Mattered Most: Who Is This For?

The brief mentions both internal team members and clients. I spent more time on this than anything else, because the answer completely changes what you build.

If this is a client-facing tool, you're now thinking about: how does it look? How do we explain bad numbers without panicking the client? Who has access to what? What if a client sees their data next to a competitor's? What if the data is wrong — who's responsible? You're building a product, not a tool.

If this is an internal tool, almost none of that applies. Your users are professionals who already understand the data. They want answers, not presentations.

I chose internal user as the primary. Not because the client-facing version isn't valuable — it obviously is — but because that's not the problem being asked about. The problem is that the team can't answer the question quickly internally. Fix that first. Everything else is a different project.

This also meant I could keep the interface very simple. No auth. No branding. No "how do we explain a bad month." Just: here's what the data says.

---

## The Hardest Part to Think Through: Data

I want to be honest here — the data layer is where this gets genuinely complicated, and I don't want to pretend otherwise.

The team uses existing tools. Those tools have APIs. In theory, you can pull from all of them. In practice:

Some APIs are well-documented and easy to work with (Google Ads, GA4). Some are inconsistent or have rate limits that make automated pulls annoying (Meta). Some CRMs have APIs that vary based on which plan you're on. And credentials — getting proper API access authorised across multiple platforms — is the kind of thing that sounds like an afternoon job but can easily take a week if the right people aren't responsive.

My honest take: the technical connection to any one of these APIs isn't that hard. Reliably connecting to four or five of them, handling errors gracefully, and making sure fresh data is there every morning — that's where the engineering effort actually lives.

That's why I separated the data pipeline from the app itself in the design. The connectors run independently. If Meta's API is having a bad day, it doesn't break the tool for the users who need to see Google Ads data. The app always reads from the store, not from live API calls.

I also deliberately didn't specify which data store beyond "BigQuery or similar." Partly because I don't know what the team already has set up. If they're already on BigQuery, great. If not, even a well-structured Google Sheet could work for v1 at low data volumes. I'd rather ship something that works than over-engineer the storage layer before I know what the actual data volumes are.

---

## What I Ruled Out and Why

A few specific things I considered and then cut:

**Automated Slack/email delivery.** My first instinct was to include this — it feels like it would save a lot of time. But then I thought about how I'd feel if I got a Slack message at 8am saying "your marketing performance is below average" and I had no idea if the numbers were right. Push notifications require trust. You build trust by letting people pull the information themselves first, verify it against what they already know, and then decide they want it pushed. I'd come back to this in v2.

**Recommendations.** "Here's what's happening" feels incomplete. "Here's what you should do about it" feels more valuable. But recommendations require context the tool doesn't have — it doesn't know that spend went up because of a specific campaign launch, or that the conversion rate drop is expected because a promotion ended. A wrong recommendation is worse than no recommendation. So I kept the tool in the "describe, don't prescribe" zone.

**Campaign-level detail.** This was genuinely tempting. Once you have channel-level data, you're one step away from campaign-level. But campaign data is an order of magnitude more complex — different naming conventions, different structures across platforms, more rows, more edge cases. And it answers a slightly different question. "How is our marketing performing?" is a channel-level question. "Which campaigns should we pause?" is a campaign-level question. Keep them separate.

**Historical trends.** Another one I wanted to include and then cut. Trend charts are only useful once you've collected enough data to have a trend. If you build this in March and look at it in April, the chart is just two data points. I'd add this after three or four months of data collection.

---

## What I'd Want to Know Before Anyone Wrote a Line of Code

If I were handing this brief to a developer tomorrow, I'd want answers to these questions first:

1. Which marketing platforms does the team actually use actively? The connector list depends entirely on this.
2. Does anyone on the team already have admin API access to those platforms, or does that need to be set up?
3. Is there already a central data store (BigQuery, Redshift, Snowflake), or would this be the first one?
4. How many client brands are we talking about? 5? 50? The data model and performance requirements are different at different scales.
5. What does "marketing performance" actually mean to the team — which metrics do they care about most? I've made assumptions (impressions, clicks, spend, conversions) but this should be validated.

None of these are showstoppers. But going into a build without answers to them leads to rework, and rework is the thing that makes small projects take three times as long as they should.

---

## What I'm Least Confident About

The plain-language summary generation. It sounds simple, but getting this right is actually subtle.

A summary that says "spend is up, conversions are down" is accurate but useless — any analyst can see that from the numbers. A summary that provides genuine interpretation requires context the tool doesn't always have. And a bad summary — one that misframes the situation — is actively harmful.

My current thinking: start with a rule-based approach (if metric X changed by more than Y%, include it in the summary). That's deterministic, explainable, and can be tuned. Once the team has built up trust in the data, layer in something more sophisticated that can actually interpret patterns. But don't start there.

---

## If I Could Do This Over

I'd have started by spending half a day with two or three actual users of this kind of tool — not asking them what they want, but watching them answer the "how is marketing performing?" question live. Seeing which tabs they open, in what order, what they ignore, what they write down. The design decisions I'd make after doing that would probably be quite different from the ones I've made here.

That's the thing about product work — the thinking is important, but it's always downstream of understanding what people actually do, not what they say they do.

---

## One Last Thing

The brief says the team won't change their tools or workflows. I've scoped entirely around that constraint, and I think that's right. But I want to flag one thing: the tool I've described sits on top of their existing tools, it doesn't replace any of them. The connectors read from their platforms using APIs that already exist. The team doesn't need to log into anything new or export anything differently.

The only thing that changes is that the answer to the question is now available in one place, at 7am, every day, without anyone having to go and get it.

That's the whole point.
