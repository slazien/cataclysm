import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

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
    authorized({ auth: session }) {
      // In dev mode (no OAuth), allow all requests through
      if (!hasOAuth) return true;
      return !!session?.user;
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
