import twitterText from "twitter-text";
// Use the provider-maintained parser for URL, emoji and Unicode weighting.
export function xCaption(text: string) {
  return twitterText.parseTweet(text);
}
