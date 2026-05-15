"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = __importDefault(require("react"));
const Layout_1 = __importDefault(require("./components/Layout/Layout"));
const Home_1 = __importDefault(require("./pages/Home/Home"));
function App() {
    return ((0, jsx_runtime_1.jsx)(Layout_1.default, { children: (0, jsx_runtime_1.jsx)(Home_1.default, {}) }));
}
exports.default = App;
//# sourceMappingURL=App.js.map