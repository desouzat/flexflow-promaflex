# FlexFlow Frontend

Modern React frontend for the FlexFlow Purchase Order Management System.

## Tech Stack

- **React 18** - UI library
- **Vite** - Build tool and dev server
- **Tailwind CSS** - Utility-first CSS framework
- **Lucide React** - Icon library
- **React Router** - Client-side routing
- **Axios** - HTTP client
- **Vitest** - Testing framework
- **React Testing Library** - Component testing

## Project Structure

```
frontend/
├── src/
│   ├── components/        # Reusable components
│   │   ├── kanban/       # Kanban-specific components
│   │   │   ├── KanbanCard.jsx
│   │   │   ├── KanbanCard.test.jsx
│   │   │   ├── KanbanColumn.jsx
│   │   │   └── KanbanColumn.test.jsx
│   │   ├── Layout.jsx    # Main layout with sidebar
│   │   └── Layout.test.jsx
│   ├── context/          # React contexts
│   │   ├── AuthContext.jsx
│   │   └── AuthContext.test.jsx
│   ├── pages/            # Page components
│   │   ├── LoginPage.jsx
│   │   ├── LoginPage.test.jsx
│   │   ├── KanbanPage.jsx
│   │   ├── KanbanPage.test.jsx
│   │   ├── ImportPage.jsx
│   │   ├── ImportPage.test.jsx
│   │   ├── DashboardPage.jsx
│   │   └── DashboardPage.test.jsx
│   ├── utils/            # Utility functions
│   │   └── api.js        # Axios instance with interceptors
│   ├── test/             # Test configuration
│   │   └── setup.js
│   ├── App.jsx           # Main app component
│   ├── App.test.jsx
│   ├── main.jsx          # Entry point
│   └── index.css         # Global styles
├── public/               # Static assets
├── index.html            # HTML template
├── package.json          # Dependencies
├── vite.config.js        # Vite configuration
├── tailwind.config.js    # Tailwind configuration
└── postcss.config.js     # PostCSS configuration
```

## Getting Started

### Prerequisites

- Node.js 18+ and npm/yarn/pnpm

### Installation

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Run tests
npm test

# Run tests with UI
npm run test:ui

# Run tests with coverage
npm run test:coverage

# Build for production
npm run build

# Preview production build
npm run preview
```

## Features

### Authentication
- JWT-based authentication
- Protected routes
- Automatic token refresh
- Persistent login state

### Kanban Board
- Visual workflow management
- Drag-and-drop support (coming soon)
- Real-time updates (coming soon)
- Search and filter functionality

### Import System
- Excel file upload
- Batch PO import
- Validation and error reporting

### Dashboard
- Key metrics and KPIs
- Visual charts and graphs
- Trend analysis

## Environment Variables

Create a `.env` file in the frontend directory:

```env
VITE_API_URL=http://localhost:8000
```

## Testing

All components include comprehensive tests:
- Unit tests for components
- Integration tests for pages
- Context and hook tests

Run tests with:
```bash
npm test
```

## API Integration

The frontend communicates with the backend API at `http://localhost:8000` by default.

API endpoints:
- `POST /auth/login` - User authentication
- `GET /kanban/pos` - Fetch purchase orders
- `POST /import/upload` - Upload Excel file
- `GET /dashboard/stats` - Dashboard statistics

## Code Quality

- ESLint for code linting
- Prettier for code formatting (recommended)
- Vitest for testing
- 100% test coverage goal

## Contributing

1. Create a feature branch
2. Write tests for new features
3. Ensure all tests pass
4. Submit a pull request

## License

Proprietary - All rights reserved
