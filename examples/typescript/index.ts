import { Demo } from './api';
import { Static } from './static'

const cli = new Demo.DemoClient();
const v: Demo.ReqAbcQuery = {};



const cli2 = new Static.StaticClient();
const v2 = cli2.docJson()