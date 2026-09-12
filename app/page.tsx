import { requireChatGPTUser } from "./chatgpt-auth";
import Studio from "./studio";
export const dynamic = "force-dynamic";
export default async function Home() {
  const user = await requireChatGPTUser("/");
  return <Studio displayName={user.displayName} />;
}
