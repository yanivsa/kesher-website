import { onRequest as __api_contact_ts_onRequest } from "/Users/ninja/Documents/Kesher/functions/api/contact.ts"
import { onRequest as ___middleware_ts_onRequest } from "/Users/ninja/Documents/Kesher/functions/_middleware.ts"

export const routes = [
    {
      routePath: "/api/contact",
      mountPath: "/api",
      method: "",
      middlewares: [],
      modules: [__api_contact_ts_onRequest],
    },
  {
      routePath: "/",
      mountPath: "/",
      method: "",
      middlewares: [___middleware_ts_onRequest],
      modules: [],
    },
  ]