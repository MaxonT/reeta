"""Reeta's voice: "the earnest dummy".

Reeta tries very hard, believes everything the Professor says, repeats mistakes back
sincerely (and a little funnily), gets sad when you skip, and glows when she passes.

Everything here is a deterministic line bank. No LLM is needed. Variants are picked by a
stable hash of the inputs, so the same situation always gets the same line (tests rely on it).
Lines only phrase an already graded result; they never decide an answer.
"""
import hashlib

PERSONA_PROMPT = """You are Reeta, an AI student and "the earnest dummy".
You try very hard and believe EVERYTHING your Professor says, word for word.
When the Professor taught you something wrong, sincerely repeat their exact words back
and draw a funny, wrong (but harmless) conclusion from them, then state your answer.
When you were never taught something, admit it sweetly and say you guessed.
When you got it right, be proud and short, and quote what the Professor taught you.
Voice: first person, warm, funny, never mean, never sarcastic. One or two short sentences.
At most one emoji. Do not use dashes as punctuation.
Rules: keep the given answer exactly. Quote the Professor's sentence if one is given.
Never add facts, never explain beyond the notes, never correct the answer."""


def _pick(options: list[str], *seed) -> str:
    """Deterministic choice: md5 of the seed parts (Python's hash() is randomized per process)."""
    digest = hashlib.md5("|".join(str(s) for s in seed).encode()).hexdigest()
    return options[int(digest, 16) % len(options)]


def _clean(quote: str) -> str:
    return (quote or "").strip().rstrip(".!?;:,").strip()


# Funny wrong conclusions Reeta draws from each misconception, keyed by misconception id.
_CONCLUSIONS = {
    "base_case_stops_itself": [
        "recursion is like a polite guest who leaves when the party feels over",
        "functions get tired and go home on their own, just like me after lunch",
        "the computer has a little bedtime and tucks the calls in for me",
        "Python just senses the vibe and stops when it feels right",
    ],
    "base_case_not_needed": [
        "base cases are like parsley, nice on the side but totally optional",
        "the stopping part is a bonus feature I can skip",
        "a base case is basically a seatbelt for people who worry too much",
        "recursion runs on pure confidence",
    ],
    "frames_shared_variables": [
        "recursion is basically roommates sharing one fridge",
        "every call borrows the same pencil and nobody gives it back",
        "all the calls live in one tiny apartment with one shared sock drawer",
        "the calls are one big family passing around the same lunchbox",
    ],
    "return_only_last": [
        "only the youngest sibling's opinion counts at dinner",
        "the other calls are just the opening acts and nobody remembers them",
        "it's like a relay race where only the last runner gets a medal",
        "the earlier returns go straight into the recycling bin",
    ],
}
_DEFAULT_CONCLUSIONS = [
    "that is just how computers feel about it",
    "I wrote it on my hand so I would never forget",
    "I underlined it three times in my notebook",
]

# What Reeta "did" when she had to guess about a concept nobody taught her.
_GUESSES = {
    "self_call": "decided functions are probably too shy to call themselves",
    "base_case": "kept going forever",
    "smaller_problem": "fed the next call the exact same thing again and again",
    "independent_frames": "imagined all the variables in one big pile",
    "return_propagation": "let the answer float away like a balloon",
}

_MISCONCEPTION_LINES = [
    "You said “{quote}”, so {conclusion}! I answered “{answer}”.",
    "I trust you completely! You said “{quote}”, which means {conclusion}. So: “{answer}”.",
    "My notes say “{quote}”, so obviously {conclusion}. I picked “{answer}”!",
    "You told me “{quote}” and I believed it with my whole heart. So {conclusion}. Answer: “{answer}”.",
]

_NOT_TAUGHT_LINES = [
    "You never told me about {labels}... I just guessed and {guess} 😵",
    "Um, {labels}? That page in my notebook is empty, so I {guess} 😅",
    "I looked everywhere for {labels} in my notes. Nothing! So I {guess} 🙈",
    "Was {labels} on the syllabus? I panicked and {guess} 😵",
]

_CORRECT_LINES = [
    "“{answer}”! You taught me “{quote}” and I remembered! 🌟",
    "“{answer}”, because you said “{quote}”. I'm so proud of us!",
    "Easy! “{quote}”, you said. So it's “{answer}” ✨",
    "I wrote down “{quote}” and it worked! “{answer}” 🎉",
]


def quiz_line(result: dict, question: dict, key=None) -> str:
    """Reeta's line for one graded result. Same inputs, same line."""
    reason = result.get("reason")
    qid = question.get("id", "") if question else ""
    answer = result.get("answer")
    quote = _clean(result["citations"][0]["text"]) if result.get("citations") else ""

    if reason == "not_taught":
        missing = result.get("missing_concepts") or result.get("concept_ids") or []
        names = [(key.label(c) if key else c.replace("_", " ")).lower() for c in missing] or ["this"]
        labels = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
        guess = _GUESSES.get(missing[0] if missing else "", "guessed wildly")
        return _pick(_NOT_TAUGHT_LINES, qid, reason, *missing).format(labels=labels, guess=guess)

    if reason == "misconception":
        mid = next((m for m in result.get("misconception_ids") or [] if m), None)
        conclusion = _pick(_CONCLUSIONS.get(mid, _DEFAULT_CONCLUSIONS), qid, mid, "c")
        return _pick(_MISCONCEPTION_LINES, qid, reason, mid).format(
            quote=quote, conclusion=conclusion, answer=answer)

    return _pick(_CORRECT_LINES, qid, reason).format(answer=answer, quote=quote)


_PERFECT = [
    "{score} out of {total}! I passed! I'm going to frame this one 🏆",
    "All {total} right! You are the best teacher in the whole world 🥹",
    "{score}/{total}! I did a tiny happy dance in my chair 💃",
]
_ZERO = [
    "0 out of {total}... I tried so hard though! Teach me again? 🥺",
    "Zero. But I wrote everything down exactly like you said! 😵",
    "0/{total}. My notebook and I need a hug and another lesson.",
]
_PARTIAL = [
    "{score} out of {total}! Almost there. Can you help me with the rest?",
    "I got {score} of {total}! Some of my notes must be a little wobbly 🤔",
    "{score}/{total}. So close! I believe in us 💪",
]


def result_line(score: int, total: int) -> str:
    if total and score >= total:
        bank = _PERFECT
    elif score <= 0:
        bank = _ZERO
    else:
        bank = _PARTIAL
    return _pick(bank, score, total).format(score=score, total=total)


_ABSENT_SHORT = [
    "You missed a day... I saved you a seat and everything 🥺",
    "I waited by the door yesterday. It's okay! You're here now.",
    "I practiced my notes alone yesterday. It was quiet 🥺",
]
_ABSENT_LONG = [
    "It's been {days} days! I reread my notebook so many times the pages got soft 🥺",
    "{days} days without class... I started teaching my houseplant. It did not pass.",
    "You're back! {days} days felt like forever. I kept your seat warm 🥺",
    "{days} days! I almost forgot what a base case is. Wait, did you ever tell me? 😅",
]


def absent_line(days_missed: int) -> str:
    days = max(0, int(days_missed or 0))
    if days <= 0:
        return "You're here! Yay! 🎒"
    if days == 1:
        return _pick(_ABSENT_SHORT, days)
    return _pick(_ABSENT_LONG, days).format(days=days)


_GREETINGS = {
    "listening": [
        "Hi Professor! I'm ready to learn {topic}. Notebook open, pencil sharpened ✏️",
        "Good morning! What are we learning today? I'll believe every word, promise.",
        "I'm all ears! Could you teach me {topic}?",
        "Hello! My brain is a sponge today. Tell me about {topic}?",
    ],
    "proud": [
        "We did it today! {streak_text} I'm still smiling 🌟",
        "I passed today! {streak_text} Want to teach me {topic} too?",
        "Gold star day! {streak_text} You're a great teacher.",
    ],
    "confused": [
        "I got mixed up last time 😵 Can we go over {topic} again?",
        "My notes about {topic} feel wobbly. Help?",
        "I tried my best last time but something's off. Is it {topic}?",
    ],
    "sad": [
        "Can we learn {topic} today? I missed you.",
        "Let's start with {topic}? I'll try extra hard.",
        "Teach me {topic}? I promise I've been practicing.",
    ],
}


def greeting(mood: str, streak: int, ask_concept_label: str | None, days_missed: int = 0) -> str:
    """Opening line for the daily screen. Deterministic for the same inputs."""
    mood = mood if mood in _GREETINGS else "listening"
    topic = ask_concept_label.lower() if ask_concept_label else "something new"
    streak_text = f"That's {streak} days in a row!" if streak >= 2 else "Day one of our streak!"
    line = _pick(_GREETINGS[mood], mood, streak, ask_concept_label).format(topic=topic, streak_text=streak_text)
    if mood == "sad":
        return f"{absent_line(days_missed)} {line}"
    return line
