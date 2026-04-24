import React, { useEffect, useState } from 'react';
import { Card } from 'react-bootstrap';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import api from '../../api/auth';

const APPROVED_STATUSES = new Set(['approved', 'completed']);
const DELAYED_STATUSES = new Set(['pending', 'delayed']);
const REJECTED_STATUSES = new Set(['rejected', 'denied', 'declined']);

const PayrollChart = () => {
  const [chartData, setChartData] = useState([]);

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const response = await api.get('/processing/history');

        const grouped = response.data.reduce((acc, curr) => {
          const normalizedStatus = String(curr.status || '').trim().toLowerCase();
          if (!curr.processed_at) return acc;

          const processedDate = new Date(curr.processed_at);
          if (Number.isNaN(processedDate.getTime())) return acc;

          const isoDay = processedDate.toISOString().slice(0, 10);
          if (!acc[isoDay]) {
            acc[isoDay] = {
              isoDay,
              label: processedDate.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }),
              totalPayout: 0,
              delayedPayout: 0,
              rejectedPayout: 0,
            };
          }

          const netPay = Number(curr.net_pay || 0);
          if (APPROVED_STATUSES.has(normalizedStatus)) {
            acc[isoDay].totalPayout += netPay;
          } else if (DELAYED_STATUSES.has(normalizedStatus)) {
            acc[isoDay].delayedPayout += netPay;
          } else if (REJECTED_STATUSES.has(normalizedStatus)) {
            acc[isoDay].rejectedPayout += netPay;
          }
          return acc;
        }, {});

        const formattedData = Object.values(grouped)
          .sort((a, b) => a.isoDay.localeCompare(b.isoDay))
          .slice(-7)
          .map(({ label, totalPayout, delayedPayout, rejectedPayout }) => ({
            name: label,
            totalPayout: Number(totalPayout.toFixed(2)),
            delayedPayout: Number(delayedPayout.toFixed(2)),
            rejectedPayout: Number(rejectedPayout.toFixed(2)),
          }));

        setChartData(formattedData);
      } catch (error) {
        console.error('Error fetching chart data:', error);
      }
    };

    fetchHistory();
  }, []);

  return (
    <Card className="border-0 shadow-sm p-4 mb-4 rounded-4">
      <h6 className="fw-bold mb-4" style={{ color: '#5A4343', fontSize: '13px' }}>PAYROLL HISTORY</h6>
      <div style={{ width: '100%', height: 280 }}>
        {chartData.length > 0 ? (
          <ResponsiveContainer>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
              <Legend />
              <XAxis
                dataKey="name"
                axisLine={false}
                tickLine={false}
                tick={{ fill: '#999', fontSize: 11 }}
              />
              <YAxis
                axisLine={false}
                tickLine={false}
                tick={{ fill: '#999', fontSize: 11 }}
                tickFormatter={(value) => `PHP ${(value / 1000).toFixed(0)}k`}
              />
              <Tooltip
                cursor={{ fill: 'rgba(210, 145, 145, 0.05)' }}
                contentStyle={{ borderRadius: '10px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)', fontSize: '12px' }}
                formatter={(value, name) => [
                  `PHP ${Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
                  name
                ]}
              />
              <Bar
                dataKey="totalPayout"
                fill="#4B8B8B"
                radius={[6, 6, 0, 0]}
                barSize={20}
                name="Total Payout"
              />
              <Bar
                dataKey="delayedPayout"
                fill="#F4A261"
                radius={[6, 6, 0, 0]}
                barSize={20}
                name="Delayed Payout"
              />
              <Bar
                dataKey="rejectedPayout"
                fill="#D29191"
                radius={[6, 6, 0, 0]}
                barSize={20}
                name="Rejected Payout"
              />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-100 d-flex align-items-center justify-content-center text-muted">
            <small>Insufficient data to generate history chart.</small>
          </div>
        )}
      </div>
    </Card>
  );
};

export default PayrollChart;
