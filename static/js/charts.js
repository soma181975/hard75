// Chart.js initialization for Hard 75 Tracker

// Common chart options
const commonOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: {
            display: false
        }
    },
    scales: {
        x: {
            grid: {
                display: false
            }
        },
        y: {
            beginAtZero: true,
            grid: {
                color: '#f3f4f6'
            }
        }
    }
};

// Initialize volume chart
function initVolumeChart(data) {
    const ctx = document.getElementById('volumeChart');
    if (!ctx || !data || data.length === 0) return;

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(d => formatDate(d.date)),
            datasets: [{
                label: 'Volume (lbs x reps)',
                data: data.map(d => d.total_volume),
                backgroundColor: 'rgba(59, 130, 246, 0.8)',
                borderRadius: 4
            }]
        },
        options: {
            ...commonOptions,
            plugins: {
                ...commonOptions.plugins,
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `Volume: ${context.raw.toLocaleString()} lbs`;
                        }
                    }
                }
            }
        }
    });
}

// Initialize steps chart
function initStepsChart(data) {
    const ctx = document.getElementById('stepsChart');
    if (!ctx || !data || data.length === 0) return;

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(d => formatDate(d.date)),
            datasets: [{
                label: 'Steps',
                data: data.map(d => d.steps),
                borderColor: 'rgb(34, 197, 94)',
                backgroundColor: 'rgba(34, 197, 94, 0.1)',
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            ...commonOptions,
            plugins: {
                ...commonOptions.plugins,
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `Steps: ${context.raw.toLocaleString()}`;
                        }
                    }
                }
            }
        }
    });
}

// Initialize exercise progression chart
function initExerciseProgressionChart(elementId, data, exerciseName) {
    const ctx = document.getElementById(elementId);
    if (!ctx || !data || data.length === 0) return;

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(d => formatDate(d.date)),
            datasets: [
                {
                    label: 'Max Weight',
                    data: data.map(d => d.max_weight),
                    borderColor: 'rgb(59, 130, 246)',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    fill: false,
                    yAxisID: 'y'
                },
                {
                    label: 'Est. 1RM',
                    data: data.map(d => d.estimated_1rm),
                    borderColor: 'rgb(168, 85, 247)',
                    backgroundColor: 'rgba(168, 85, 247, 0.1)',
                    fill: false,
                    borderDash: [5, 5],
                    yAxisID: 'y'
                }
            ]
        },
        options: {
            ...commonOptions,
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                },
                title: {
                    display: true,
                    text: exerciseName
                }
            }
        }
    });
}

// Initialize calories chart
function initCaloriesChart(data) {
    const ctx = document.getElementById('caloriesChart');
    if (!ctx || !data || data.length === 0) return;

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(d => formatDate(d.date)),
            datasets: [{
                label: 'Calories',
                data: data.map(d => d.calories),
                backgroundColor: 'rgba(249, 115, 22, 0.8)',
                borderRadius: 4
            }]
        },
        options: {
            ...commonOptions,
            plugins: {
                ...commonOptions.plugins,
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `Calories: ${context.raw.toLocaleString()}`;
                        }
                    }
                }
            }
        }
    });
}

// Initialize protein chart
function initProteinChart(data) {
    const ctx = document.getElementById('proteinChart');
    if (!ctx || !data || data.length === 0) return;

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(d => formatDate(d.date)),
            datasets: [{
                label: 'Protein (g)',
                data: data.map(d => d.protein_g),
                borderColor: 'rgb(139, 92, 246)',
                backgroundColor: 'rgba(139, 92, 246, 0.1)',
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            ...commonOptions,
            plugins: {
                ...commonOptions.plugins,
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `Protein: ${context.raw}g`;
                        }
                    }
                }
            }
        }
    });
}

// Initialize macros breakdown chart (pie/doughnut)
function initMacrosChart(protein, carbs, fat) {
    const ctx = document.getElementById('macrosChart');
    if (!ctx) return;

    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Protein', 'Carbs', 'Fat'],
            datasets: [{
                data: [protein, carbs, fat],
                backgroundColor: [
                    'rgba(139, 92, 246, 0.8)',  // Purple for protein
                    'rgba(59, 130, 246, 0.8)',   // Blue for carbs
                    'rgba(249, 115, 22, 0.8)'    // Orange for fat
                ],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = Math.round((context.raw / total) * 100);
                            return `${context.label}: ${context.raw}g (${percentage}%)`;
                        }
                    }
                }
            }
        }
    });
}

// Helper: Format date for display
function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// Helper: Fetch and render exercise progression
async function loadExerciseProgression(exerciseName, elementId) {
    try {
        const response = await fetch(`/api/workouts/exercises/${encodeURIComponent(exerciseName)}/progression`);
        const data = await response.json();
        initExerciseProgressionChart(elementId, data, exerciseName);
    } catch (error) {
        console.error('Failed to load exercise progression:', error);
    }
}

// Helper: Fetch and render today's nutrition
async function loadTodayNutrition() {
    try {
        const response = await fetch('/api/meals/today');
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Failed to load nutrition data:', error);
        return null;
    }
}
