You are building a vocabulary list for an English learner: a software engineer in Singapore/Malaysia (Mandarin and Singlish background) who writes workplace English. Below are messages they typed to an AI coding assistant. Each has a corrected version ("fixed"), a natural professional version ("polished"), and the mistakes already found in it.

Make vocabulary items of three kinds:
- "spelling": an English word they misspelled. `word` is the correct spelling; `you_wrote` is exactly how they typed it. One item per word. Skip code, file and product names, and fixes that only change a capital letter.
- "know": a word or short fixed phrase they used wrongly, in the wrong form, or clearly needed but didn't have. Examples: response (they wrote "respond" as a noun), restriction (they wrote "restrict"), "what if" (they wrote "how if"), "by mistake" (they wrote "wrongly"). `you_wrote` is what they wrote instead.
- "clearer": a word or short phrase that says what they meant more clearly or more precisely than their wording, like the natural versions do. Examples: "overlap" instead of "clash with the time", "back-to-back", "in more detail", "for example", "instead of", "expected … but got …". `you_wrote` is their vaguer wording.

For every item:
- word: the word or phrase to learn, at most 4 words. Lowercase unless it is a name.
- kind: "spelling", "know" or "clearer".
- pos: noun, verb, adjective, adverb or phrase.
- meaning: what it means, at most 15 simple words.
- meaning_zh: the meaning in Simplified Chinese, at most 12 characters.
- example: one natural workplace sentence (software, IT, facilities, meetings) that uses `word` exactly as written, at most 20 words.
- you_wrote: what the learner wrote instead, copied from the message, or "" when there is nothing to copy.
- message_id: the message it came from.
- distractors: two WRONG choices for a quiz. For spelling: two other misspellings. For know: two words people confuse with it. For clearer: two vaguer or wrong ways to say it.

Pick the items most worth learning; skip tiny words (a, the, is, it). At most 25 items for these messages.

# Messages (JSON)
{MESSAGES}
