// Import Bootstrap CSS
import "bootstrap/dist/css/bootstrap.min.css";

// Import Bootstrap Icons
import "bootstrap-icons/font/bootstrap-icons.css";

// Import Bootstrap JS and expose globally
import * as bootstrap from "bootstrap/dist/js/bootstrap.bundle.min.js";
window.bootstrap = bootstrap.default ?? bootstrap;

// Import Luxon
import * as luxon from "luxon";

// Note: luxon is no longer made globally available as window.luxon
// Modules should import it directly from "luxon" if needed.
