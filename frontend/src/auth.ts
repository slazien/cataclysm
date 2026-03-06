import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

const devAuthBypass = process.env.DEV_AUTH_BYPASS === "true";
const hasOAuth = !!(process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET);

const providers = hasOAuth
  ? [
      Google({
        clientId: process.env.GOOGLE_CLIENT_ID!,
        clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
      }),
    ]
  : [];

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers,
  session: { strategy: "jwt" },
  callbacks: {
    authorized() {
      // Allow all requests through — auth requirements are handled at the
      // component level. The middleware still runs and attaches session info
      // for authenticated users. Anonymous users can reach the WelcomeScreen
      // and upload flow; auth-gated features (Progress, Share, Chat) check
      // for a session in their own components.
      return true;
    },
    jwt({ token, user, profile }) {
      if (user) {
        token.sub = user.id;
      }
      if (profile) {
        token.picture = profile.picture as string | undefined;
      }
      return token;
    },
    session({ session, token }) {
      if (session.user && token.sub) {
        session.user.id = token.sub;
      }
      return session;
    },
  },
});
