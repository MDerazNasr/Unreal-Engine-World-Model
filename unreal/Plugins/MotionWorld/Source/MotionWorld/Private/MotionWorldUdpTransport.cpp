#include "MotionWorldUdpTransport.h"

#include "Common/UdpSocketBuilder.h"
#include "Interfaces/IPv4/IPv4Address.h"
#include "Interfaces/IPv4/IPv4Endpoint.h"
#include "SocketSubsystem.h"
#include "Sockets.h"

namespace MotionWorld
{
bool FMotionWorldUdpTransportConfig::IsValid() const
{
	return LocalPort > 0
		&& RemotePort > 0
		&& LocalPort != RemotePort
		&& MaxInboundDatagramBytes > 0
		&& MaxInboundDatagramBytes < MaxUdpPayloadBytes
		&& MaxOutboundDatagramBytes > 0
		&& MaxOutboundDatagramBytes < MaxUdpPayloadBytes
		&& MaxDatagramsPerPoll > 0
		&& MaxDatagramsPerPoll <= 1024;
}

FMotionWorldUdpTransport::~FMotionWorldUdpTransport()
{
	Close();
}

bool FMotionWorldUdpTransport::Open(const FMotionWorldUdpTransportConfig& InConfig)
{
	Close();
	if (!InConfig.IsValid())
	{
		return false;
	}

	Config = InConfig;
	SocketSubsystem = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM);
	if (!SocketSubsystem)
	{
		return false;
	}

	const FIPv4Endpoint LocalEndpoint(FIPv4Address::InternalLoopback, Config.LocalPort);
	Socket = FUdpSocketBuilder(TEXT("MotionWorldControlUdp"))
		.AsNonBlocking()
		.BoundToEndpoint(LocalEndpoint)
		.WithReceiveBufferSize(MaxUdpPayloadBytes * 2)
		.WithSendBufferSize(MaxUdpPayloadBytes * 2);
	if (!Socket)
	{
		SocketSubsystem = nullptr;
		return false;
	}

	RemoteAddress = FIPv4Endpoint(
		FIPv4Address::InternalLoopback,
		Config.RemotePort).ToInternetAddr();
	ReceiveBuffer.SetNumUninitialized(MaxUdpPayloadBytes);
	return true;
}

void FMotionWorldUdpTransport::Close()
{
	RemoteAddress.Reset();
	ReceiveBuffer.Reset();
	if (Socket && SocketSubsystem)
	{
		SocketSubsystem->DestroySocket(Socket);
	}
	Socket = nullptr;
	SocketSubsystem = nullptr;
}

bool FMotionWorldUdpTransport::Send(const TConstArrayView<uint8> Payload)
{
	if (!Socket || !RemoteAddress.IsValid()
		|| Payload.IsEmpty()
		|| Payload.Num() > Config.MaxOutboundDatagramBytes)
	{
		return false;
	}

	int32 BytesSent = 0;
	return Socket->SendTo(
		Payload.GetData(),
		Payload.Num(),
		BytesSent,
		*RemoteAddress)
		&& BytesSent == Payload.Num();
}

FMotionWorldUdpPollResult FMotionWorldUdpTransport::Poll()
{
	FMotionWorldUdpPollResult Result;
	if (!Socket || !SocketSubsystem || !RemoteAddress.IsValid())
	{
		return Result;
	}

	for (int32 Index = 0; Index < Config.MaxDatagramsPerPoll; ++Index)
	{
		uint32 PendingBytes = 0;
		if (!Socket->HasPendingData(PendingBytes))
		{
			break;
		}

		TSharedRef<FInternetAddr> SenderAddress = SocketSubsystem->CreateInternetAddr();
		int32 BytesRead = 0;
		const bool bReceived = Socket->RecvFrom(
			ReceiveBuffer.GetData(),
			ReceiveBuffer.Num(),
			BytesRead,
			*SenderAddress);
		if (!bReceived)
		{
			break;
		}

		++Result.DatagramsRead;
		if (*SenderAddress != *RemoteAddress)
		{
			++Result.RejectedUnknownSender;
			continue;
		}
		if (BytesRead <= 0
			|| BytesRead > Config.MaxInboundDatagramBytes)
		{
			++Result.RejectedOversizedOrEmpty;
			continue;
		}

		TArray<uint8>& Payload = Result.Payloads.AddDefaulted_GetRef();
		Payload.Append(ReceiveBuffer.GetData(), BytesRead);
	}

	Result.bPollBudgetExhausted =
		Result.DatagramsRead == Config.MaxDatagramsPerPoll;
	return Result;
}
} // namespace MotionWorld
