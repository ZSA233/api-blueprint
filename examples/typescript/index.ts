import { createClients as createApiClients } from "./api/transports/http/api";
import type * as ApiDemoTypes from "./api/routes/api/demo/types";
import { createClients as createStaticClients } from "./static/transports/http/static";

const apiClients = createApiClients();
const cli = apiClients.demoClient;
const v: ApiDemoTypes.AbcQuery = {};

const staticClients = createStaticClients();
const cli2 = staticClients.staticClient;
const v2 = cli2.docJson()
