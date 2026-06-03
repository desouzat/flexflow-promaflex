const esbuild = require('../frontend/node_modules/esbuild');
esbuild.build({
    entryPoints: ['frontend/src/pages/KanbanPage.jsx'],
    bundle: false,
    write: false,
    logLevel: 'verbose'
}).catch(err => {
    console.error("Esbuild compilation failed:");
    if (err.errors) {
        err.errors.forEach(e => {
            console.error(`Error: ${e.text} at ${e.location.file}:${e.location.line}:${e.location.column}`);
            console.error(`Line content: "${e.location.lineText}"`);
        });
    } else {
        console.error(err);
    }
});
